from __future__ import annotations

import datetime as _dt
import inspect
import mimetypes

from sanic import Sanic, Request, Blueprint, json as _json_response, html, raw
from sanic.exceptions import NotFound

from oxyde_admin.adapters.base import AbstractAdapter, STATIC_DIR


def _json_default(obj):
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def json(body, **kwargs):
    """Wrapper around ``sanic.json`` with datetime-aware serialization."""
    kwargs.setdefault("default", _json_default)
    return _json_response(body, **kwargs)


class SanicAdmin(AbstractAdapter):
    """Sanic adapter for Oxyde Admin."""

    def __init__(self, prefix: str = "/admin", **kwargs) -> None:
        super().__init__(**kwargs)
        self.prefix = prefix
        self._blueprint = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def blueprint(self) -> Blueprint:
        """Return a Blueprint that can be registered on any Sanic app.

        The host application must also register the exception handlers
        so that admin-raised errors are converted to JSON responses::

            admin.register_exception_handlers(app)
            app.blueprint(admin.blueprint)
        """
        if self._blueprint is None:
            self._blueprint = self._build_blueprint()
        return self._blueprint

    def register_exception_handlers(self, app: Sanic) -> None:
        """Register exception-to-JSON and SPA fallback handlers on the app.

        Sanic's router cannot combine ``<path:path>`` catch-all with
        parameterized API routes in the same blueprint, so the SPA
        fallback is implemented as a ``NotFound`` error handler instead.
        """
        self._register_exception_handlers(app)

    # ------------------------------------------------------------------
    # AbstractAdapter implementation
    # ------------------------------------------------------------------

    def _build_app(self) -> Sanic:
        app = Sanic("OxydeAdmin", configure_logging=False)

        self._register_exception_handlers(app)
        app.blueprint(self.blueprint)

        return app

    def _register_auth_middleware(self, app) -> None:
        pass

    def _register_exception_handlers(self, app: Sanic) -> None:
        for exc_cls, (status_code, detail_fn) in self.EXCEPTION_MAP.items():

            def _make_handler(_status=status_code, _fn=detail_fn):
                async def handler(request: Request, exception):
                    detail = _fn(exception)
                    return json({"detail": detail}, status=_status)

                return handler

            app.error_handler.add(exc_cls, _make_handler())

        # SPA fallback: any 404 under the admin prefix serves index.html.
        # Sanic's router cannot combine <path:path> catch-all with
        # parameterized API routes, so we handle it via NotFound instead.
        admin = self

        async def spa_fallback(request: Request, exception):
            if not request.path.startswith(admin.prefix):
                raise exception
            path = request.path[len(admin.prefix) :].lstrip("/")
            static_file = admin._resolve_static_file(path)
            if static_file is not None:
                mime, _ = mimetypes.guess_type(str(static_file))
                return raw(
                    static_file.read_bytes(),
                    content_type=mime or "application/octet-stream",
                )
            rendered = admin._render_index_html(admin.prefix)
            if rendered is not None:
                return html(rendered)
            return json({"detail": "Frontend not built"}, status=404)

        app.error_handler.add(NotFound, spa_fallback)

    def _register_routes(self, app) -> None:
        pass

    def _register_static(self, app) -> None:
        pass

    # ------------------------------------------------------------------
    # Blueprint construction
    # ------------------------------------------------------------------

    def _build_blueprint(self) -> Blueprint:
        bp = Blueprint("oxyde_admin", url_prefix=self.prefix)
        admin = self
        api_prefix = self.prefix + "/api/"
        config_path = api_prefix + "config"

        # -- Auth middleware ------------------------------------------------

        if self.auth_check is not None:
            check = self.auth_check

            @bp.on_request
            async def auth_middleware(request: Request):
                path = request.path.rstrip("/")
                if not path.startswith(api_prefix.rstrip("/")):
                    return None
                if path == config_path:
                    return None
                if inspect.iscoroutinefunction(check):
                    allowed = await check(request)
                else:
                    allowed = check(request)
                if not allowed:
                    return json({"detail": "Unauthorized"}, status=401)
                return None

        # -- API routes ----------------------------------------------------

        @bp.get("/api/config")
        async def admin_config(request: Request):
            return json(admin._build_config())

        @bp.get("/api/models")
        async def models_list(request: Request):
            return json(admin._build_models_list())

        @bp.get("/api/models/counts")
        async def models_counts(request: Request):
            return json(await admin._build_models_counts())

        @bp.get("/api/<model_name:str>/schema")
        async def model_schema(request: Request, model_name: str):
            return json(await admin._handle_schema(model_name))

        @bp.get("/api/<model_name:str>")
        async def model_list(request: Request, model_name: str):
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 25))
            ordering = request.args.get("ordering")
            search = request.args.get("search")
            return json(
                await admin._handle_list(
                    model_name,
                    request.args,
                    page,
                    per_page,
                    ordering,
                    search,
                )
            )

        @bp.get("/api/<model_name:str>/options")
        async def model_options(request: Request, model_name: str):
            search = request.args.get("search")
            limit = int(request.args.get("limit", 25))
            include = request.args.get("include")
            include_list = include.split(",") if include else None
            return json(
                await admin._handle_options(
                    model_name, search=search, limit=limit, include=include_list
                )
            )

        @bp.get("/api/<model_name:str>/export")
        async def model_export(request: Request, model_name: str):
            fmt = request.args.get("format", "csv")
            ordering = request.args.get("ordering")
            search = request.args.get("search")
            ids = request.args.get("ids")
            id_list = ids.split(",") if ids else None
            stream, media_type, filename = await admin._handle_export(
                model_name,
                request.args,
                fmt,
                ordering,
                search,
                ids=id_list,
            )
            response = await request.respond(
                content_type=media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
            )
            async for chunk in stream:
                await response.send(chunk)
            await response.eof()

        @bp.get("/api/<model_name:str>/<pk:str>")
        async def model_get(request: Request, model_name: str, pk: str):
            return json(await admin._handle_get(model_name, pk))

        @bp.post("/api/<model_name:str>")
        async def model_create(request: Request, model_name: str):
            data = request.json
            return json(await admin._handle_create(model_name, data), status=201)

        @bp.put("/api/<model_name:str>/<pk:str>")
        async def model_update(request: Request, model_name: str, pk: str):
            data = request.json
            return json(await admin._handle_update(model_name, pk, data))

        @bp.delete("/api/<model_name:str>/<pk:str>")
        async def model_delete(request: Request, model_name: str, pk: str):
            return json(await admin._handle_delete(model_name, pk))

        @bp.post("/api/<model_name:str>/bulk-delete")
        async def model_bulk_delete(request: Request, model_name: str):
            body = request.json
            return json(await admin._handle_bulk_delete(model_name, body["ids"]))

        @bp.post("/api/<model_name:str>/bulk-update")
        async def model_bulk_update(request: Request, model_name: str):
            body = request.json
            return json(
                await admin._handle_bulk_update(model_name, body["ids"], body["data"])
            )

        # -- Static & SPA -------------------------------------------------

        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            bp.static("/assets", assets_dir, name="oxyde_admin_assets")

        @bp.get("/")
        async def index(request: Request):
            rendered = admin._render_index_html(admin.prefix)
            if rendered is not None:
                return html(rendered)
            return json({"detail": "Frontend not built"}, status=404)

        return bp
