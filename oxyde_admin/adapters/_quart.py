from __future__ import annotations

import datetime as _dt
import inspect
import json as _json
import mimetypes

from quart import Quart, Blueprint, request, Response

from oxyde_admin.adapters.base import AbstractAdapter, STATIC_DIR


def _json_default(obj):
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _json_response(body, status=200, headers=None):
    """Build a JSON response with datetime-aware serialization."""
    data = _json.dumps(body, default=_json_default)
    resp = Response(data, status=status, content_type="application/json")
    if headers:
        for k, v in headers.items():
            resp.headers[k] = v
    return resp


class QuartAdmin(AbstractAdapter):
    """Quart adapter for Oxyde Admin.

    Usage::

        admin = QuartAdmin(title="My Admin")
        admin.register(User, ...)

        app = Quart(__name__)
        admin.init_app(app)
    """

    def __init__(self, prefix: str = "/admin", **kwargs) -> None:
        super().__init__(**kwargs)
        self.prefix = prefix

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init_app(self, app: Quart) -> None:
        """Register the admin on a Quart application.

        This registers the blueprint (routes + auth middleware),
        exception handlers, and SPA fallback on the host app.
        """
        app.register_blueprint(self._build_blueprint())
        self._register_exception_handlers(app)

    # ------------------------------------------------------------------
    # AbstractAdapter implementation
    # ------------------------------------------------------------------

    def _build_app(self) -> Quart:
        app = Quart(__name__, static_folder=None)
        self.init_app(app)
        return app

    def _register_auth_middleware(self, app) -> None:
        pass

    def _register_routes(self, app) -> None:
        pass

    def _register_static(self, app) -> None:
        pass

    def _register_exception_handlers(self, app: Quart) -> None:
        for exc_cls, (status_code, detail_fn) in self.EXCEPTION_MAP.items():

            def _make_handler(_status=status_code, _fn=detail_fn):
                async def handler(exc):
                    detail = _fn(exc)
                    return _json_response({"detail": detail}, status=_status)

                return handler

            app.register_error_handler(exc_cls, _make_handler())

        # SPA fallback: any 404 under the admin prefix serves index.html.
        admin = self

        async def spa_fallback(exc):
            path = request.path
            if not path.startswith(admin.prefix):
                return _json_response({"detail": "Not found"}, status=404)
            rel = path[len(admin.prefix) :].lstrip("/")
            static_file = admin._resolve_static_file(rel)
            if static_file is not None:
                mime, _ = mimetypes.guess_type(str(static_file))
                return Response(
                    static_file.read_bytes(),
                    content_type=mime or "application/octet-stream",
                )
            rendered = admin._render_index_html(admin.prefix)
            if rendered is not None:
                return Response(rendered, content_type="text/html")
            return _json_response({"detail": "Frontend not built"}, status=404)

        app.register_error_handler(404, spa_fallback)

    # ------------------------------------------------------------------
    # Blueprint construction (internal)
    # ------------------------------------------------------------------

    def _build_blueprint(self) -> Blueprint:
        bp = Blueprint("oxyde_admin", __name__, url_prefix=self.prefix)
        admin = self
        api_prefix = self.prefix.rstrip("/") + "/api/"
        config_path = api_prefix.rstrip("/") + "/config"

        # -- Auth middleware ------------------------------------------------

        if self.auth_check is not None:
            check = self.auth_check

            @bp.before_request
            async def auth_middleware():
                path = request.path.rstrip("/")
                if not path.startswith(api_prefix.rstrip("/")):
                    return None
                if path == config_path:
                    return None
                if inspect.iscoroutinefunction(check):
                    allowed = await check(request._get_current_object())
                else:
                    allowed = check(request._get_current_object())
                if not allowed:
                    return _json_response({"detail": "Unauthorized"}, status=401)
                return None

        # -- API routes ----------------------------------------------------

        @bp.get("/api/config")
        async def admin_config():
            return _json_response(admin._build_config())

        @bp.get("/api/models")
        async def models_list():
            return _json_response(admin._build_models_list())

        @bp.get("/api/models/counts")
        async def models_counts():
            return _json_response(await admin._build_models_counts())

        @bp.get("/api/<model_name>/schema")
        async def model_schema(model_name: str):
            return _json_response(await admin._handle_schema(model_name))

        @bp.get("/api/<model_name>")
        async def model_list(model_name: str):
            page = request.args.get("page", 1, type=int)
            per_page = request.args.get("per_page", 25, type=int)
            ordering = request.args.get("ordering")
            search = request.args.get("search")
            return _json_response(
                await admin._handle_list(
                    model_name,
                    request.args,
                    page,
                    per_page,
                    ordering,
                    search,
                )
            )

        @bp.get("/api/<model_name>/options")
        async def model_options(model_name: str):
            search = request.args.get("search")
            limit = request.args.get("limit", 25, type=int)
            include = request.args.get("include")
            include_list = include.split(",") if include else None
            return _json_response(
                await admin._handle_options(
                    model_name, search=search, limit=limit, include=include_list
                )
            )

        @bp.get("/api/<model_name>/export")
        async def model_export(model_name: str):
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

            async def generate():
                async for chunk in stream:
                    yield chunk.encode() if isinstance(chunk, str) else chunk

            return Response(
                generate(),
                content_type=media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
            )

        @bp.get("/api/<model_name>/<pk>")
        async def model_get(model_name: str, pk: str):
            return _json_response(await admin._handle_get(model_name, pk))

        @bp.post("/api/<model_name>")
        async def model_create(model_name: str):
            data = await request.get_json()
            return _json_response(
                await admin._handle_create(model_name, data), status=201
            )

        @bp.put("/api/<model_name>/<pk>")
        async def model_update(model_name: str, pk: str):
            data = await request.get_json()
            return _json_response(await admin._handle_update(model_name, pk, data))

        @bp.delete("/api/<model_name>/<pk>")
        async def model_delete(model_name: str, pk: str):
            return _json_response(await admin._handle_delete(model_name, pk))

        @bp.post("/api/<model_name>/bulk-delete")
        async def model_bulk_delete(model_name: str):
            body = await request.get_json()
            return _json_response(
                await admin._handle_bulk_delete(model_name, body["ids"])
            )

        @bp.post("/api/<model_name>/bulk-update")
        async def model_bulk_update(model_name: str):
            body = await request.get_json()
            return _json_response(
                await admin._handle_bulk_update(model_name, body["ids"], body["data"])
            )

        # -- Static & SPA -------------------------------------------------

        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            bp.static_folder = str(assets_dir)
            bp.static_url_path = "/assets"

        @bp.get("/")
        async def index():
            rendered = admin._render_index_html(admin.prefix)
            if rendered is not None:
                return Response(rendered, content_type="text/html")
            return _json_response({"detail": "Frontend not built"}, status=404)

        return bp
