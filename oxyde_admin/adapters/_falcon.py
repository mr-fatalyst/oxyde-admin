from __future__ import annotations

import json as _json
import mimetypes

import falcon
import falcon.asgi

from oxyde_admin.adapters.base import AbstractAdapter, STATIC_DIR, json_default
from oxyde_admin.auth import AuthRequest


def _set_json(resp, body, status=200):
    """Set a JSON response with datetime-aware serialization."""
    resp.text = _json.dumps(body, default=json_default)
    resp.content_type = falcon.MEDIA_JSON
    resp.status = status


# ------------------------------------------------------------------
# Auth middleware
# ------------------------------------------------------------------


class _AuthMiddleware:
    def __init__(self, admin):
        self.admin = admin

    async def process_request(self, req, resp):
        prefix = self.admin.prefix.rstrip("/")
        path = req.path
        if not path.startswith(prefix):
            return
        rel = path[len(prefix) :]
        if not self.admin._requires_auth(rel):
            return
        user = await self.admin._authenticate(
            AuthRequest(
                headers={k.lower(): v for k, v in req.headers.items()},
                cookies=req.cookies,
                path=rel,
                method=req.method,
                native=req,
            )
        )
        if user is None:
            _set_json(resp, {"detail": "Unauthorized"}, status=401)
            resp.complete = True


# ------------------------------------------------------------------
# Resource classes
# ------------------------------------------------------------------


class ConfigResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp):
        _set_json(resp, self.admin._build_config())


class LoginResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_post(self, req, resp):
        body = await req.get_media()
        _set_json(resp, await self.admin._handle_login(body))


class ModelsResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp):
        _set_json(resp, self.admin._build_models_list())


class ModelsCountsResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp):
        _set_json(resp, await self.admin._build_models_counts())


class SchemaResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp, model_name):
        _set_json(resp, await self.admin._handle_schema(model_name))


class ModelResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp, model_name):
        page = self.admin._int_param(req.params, "page", 1)
        per_page = self.admin._int_param(req.params, "per_page", 25)
        ordering = req.get_param("ordering")
        search = req.get_param("search")
        _set_json(
            resp,
            await self.admin._handle_list(
                model_name,
                req.params,
                page,
                per_page,
                ordering,
                search,
            ),
        )

    async def on_post(self, req, resp, model_name):
        data = await req.get_media()
        _set_json(
            resp,
            await self.admin._handle_create(model_name, data),
            status=201,
        )


class ModelItemResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp, model_name, pk):
        _set_json(resp, await self.admin._handle_get(model_name, pk))

    async def on_patch(self, req, resp, model_name, pk):
        data = await req.get_media()
        _set_json(resp, await self.admin._handle_update(model_name, pk, data))

    async def on_delete(self, req, resp, model_name, pk):
        _set_json(resp, await self.admin._handle_delete(model_name, pk))


class OptionsResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp, model_name):
        search = req.get_param("search")
        limit = self.admin._int_param(req.params, "limit", 25)
        include = req.get_param("include")
        include_list = include.split(",") if include else None
        _set_json(
            resp,
            await self.admin._handle_options(
                model_name,
                search=search,
                limit=limit,
                include=include_list,
            ),
        )


class ExportResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_get(self, req, resp, model_name):
        fmt = req.get_param("format") or "csv"
        ordering = req.get_param("ordering")
        search = req.get_param("search")
        ids = req.get_param("ids")
        id_list = ids.split(",") if ids else None
        stream, media_type, filename = await self.admin._handle_export(
            model_name,
            req.params,
            fmt,
            ordering,
            search,
            ids=id_list,
        )

        async def generate():
            async for chunk in stream:
                yield chunk.encode() if isinstance(chunk, str) else chunk

        resp.content_type = media_type
        resp.set_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        resp.stream = generate()


class BulkDeleteResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_post(self, req, resp, model_name):
        body = await req.get_media()
        _set_json(
            resp,
            await self.admin._handle_bulk_delete(
                model_name, self.admin._bulk_ids(body)
            ),
        )


class BulkUpdateResource:
    def __init__(self, admin):
        self.admin = admin

    async def on_post(self, req, resp, model_name):
        body = await req.get_media()
        ids, data = self.admin._bulk_payload(body)
        _set_json(
            resp,
            await self.admin._handle_bulk_update(model_name, ids, data),
        )


# ------------------------------------------------------------------
# Adapter
# ------------------------------------------------------------------


class FalconAdmin(AbstractAdapter):
    """Falcon adapter for Oxyde Admin.

    Usage::

        admin = FalconAdmin(title="My Admin")
        admin.register(User, ...)

        app = falcon.asgi.App()
        admin.init_app(app)
    """

    def __init__(self, prefix: str = "/admin", **kwargs) -> None:
        super().__init__(**kwargs)
        self.prefix = prefix

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init_app(self, app: falcon.asgi.App) -> None:
        """Register the admin on a Falcon ASGI application."""
        if self.auth_provider is not None:
            self._register_auth_middleware(app)
        self._register_routes(app)
        self._register_exception_handlers(app)
        self._register_static(app)

    # ------------------------------------------------------------------
    # AbstractAdapter implementation
    # ------------------------------------------------------------------

    def _build_app(self) -> falcon.asgi.App:
        app = falcon.asgi.App()
        self.init_app(app)
        return app

    def _register_auth_middleware(self, app) -> None:
        app.add_middleware(_AuthMiddleware(self))

    def _register_routes(self, app) -> None:
        p = self.prefix.rstrip("/")
        app.add_route(f"{p}/api/config", ConfigResource(self))
        app.add_route(f"{p}/api/login", LoginResource(self))
        app.add_route(f"{p}/api/models", ModelsResource(self))
        app.add_route(f"{p}/api/models/counts", ModelsCountsResource(self))
        app.add_route(f"{p}/api/{{model_name}}/schema", SchemaResource(self))
        app.add_route(f"{p}/api/{{model_name}}", ModelResource(self))
        app.add_route(f"{p}/api/{{model_name}}/options", OptionsResource(self))
        app.add_route(f"{p}/api/{{model_name}}/export", ExportResource(self))
        app.add_route(f"{p}/api/{{model_name}}/{{pk}}", ModelItemResource(self))
        app.add_route(
            f"{p}/api/{{model_name}}/bulk-delete",
            BulkDeleteResource(self),
        )
        app.add_route(
            f"{p}/api/{{model_name}}/bulk-update",
            BulkUpdateResource(self),
        )

    def _register_exception_handlers(self, app) -> None:
        for exc_cls, (status_code, detail_fn) in self.EXCEPTION_MAP.items():

            def _make_handler(_status=status_code, _fn=detail_fn):
                async def handler(req, resp, ex, params):
                    _set_json(resp, {"detail": _fn(ex)}, status=_status)

                return handler

            app.add_error_handler(exc_cls, _make_handler())

    def _register_static(self, app) -> None:
        p = self.prefix.rstrip("/")
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.add_static_route(f"{p}/assets", str(assets_dir))

        admin = self

        async def spa_fallback(req, resp):
            path = req.path
            if not path.startswith(admin.prefix):
                _set_json(resp, {"detail": "Not found"}, status=404)
                return
            rel = path[len(admin.prefix) :].lstrip("/")
            static_file = admin._resolve_static_file(rel)
            if static_file is not None:
                mime, _ = mimetypes.guess_type(str(static_file))
                resp.content_type = mime or "application/octet-stream"
                resp.data = static_file.read_bytes()
                return
            rendered = admin._render_index_html(admin.prefix)
            if rendered is not None:
                resp.content_type = "text/html"
                resp.text = rendered
                return
            _set_json(resp, {"detail": "Frontend not built"}, status=404)

        app.add_sink(spa_fallback, prefix=p)
