from __future__ import annotations

import inspect

from litestar import Litestar, Request, get, post, put, delete
from litestar.params import Parameter
from litestar.static_files import StaticFilesConfig
from litestar.openapi import OpenAPIConfig
from litestar.response import Response, File, Stream
from litestar.types import ASGIApp, Receive, Scope, Send

from oxyde_admin.adapters.base import AbstractAdapter, STATIC_DIR


class LitestarAdmin(AbstractAdapter):
    """Litestar adapter for Oxyde Admin."""

    def _build_app(self) -> Litestar:
        handlers = self._build_route_handlers()

        middleware = []
        if self.auth_check is not None:
            middleware.append(self._create_auth_middleware())

        exception_handlers = self._build_exception_handlers()

        static_configs = []
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            static_configs.append(
                StaticFilesConfig(directories=[assets_dir], path="/assets")
            )

        return Litestar(
            route_handlers=handlers,
            middleware=middleware,
            exception_handlers=exception_handlers,
            static_files_config=static_configs,
            openapi_config=OpenAPIConfig(
                title="Oxyde Admin", version=self.version, path=None
            ),
        )

    def _register_auth_middleware(self, app) -> None:
        # Litestar builds middleware at app creation time,
        # so this is handled via _create_auth_middleware() in _build_app().
        pass

    def _register_exception_handlers(self, app) -> None:
        # Litestar registers exception handlers at app creation time,
        # so this is handled via _build_exception_handlers() in _build_app().
        pass

    def _register_routes(self, app) -> None:
        # Litestar registers route handlers at app creation time,
        # so this is handled via _build_route_handlers() in _build_app().
        pass

    def _register_static(self, app) -> None:
        # Litestar configures static files at app creation time,
        # so this is handled in _build_app().
        pass

    # ------------------------------------------------------------------
    # Auth middleware
    # ------------------------------------------------------------------

    def _create_auth_middleware(self):
        check = self.auth_check

        def middleware_factory(app: ASGIApp) -> ASGIApp:
            async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
                if scope["type"] != "http":
                    await app(scope, receive, send)
                    return

                path = scope.get("path", "")
                if not path.startswith("/api/") or path.rstrip("/") == "/api/config":
                    await app(scope, receive, send)
                    return

                request = Request(scope)
                if inspect.iscoroutinefunction(check):
                    allowed = await check(request)
                else:
                    allowed = check(request)

                if not allowed:
                    body = b'{"detail":"Unauthorized"}'
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 401,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()),
                            ],
                        }
                    )
                    await send({"type": "http.response.body", "body": body})
                    return

                await app(scope, receive, send)

            return middleware

        return middleware_factory

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------

    def _build_exception_handlers(self) -> dict:
        handlers = {}
        for exc_cls, (status_code, detail_fn) in self.EXCEPTION_MAP.items():

            def _make_handler(_status=status_code, _fn=detail_fn):
                async def handler(request: Request, exc) -> Response:
                    detail = _fn(exc)
                    return Response(content={"detail": detail}, status_code=_status)

                return handler

            handlers[exc_cls] = _make_handler()
        return handlers

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    def _build_route_handlers(self) -> list:
        admin = self

        @get("/api/config")
        async def admin_config() -> dict:
            return admin._build_config()

        @get("/api/models")
        async def models_list() -> list[dict]:
            return admin._build_models_list()

        @get("/api/models/counts")
        async def models_counts() -> dict[str, int]:
            return await admin._build_models_counts()

        @get("/api/{model_name:str}/schema")
        async def model_schema(model_name: str) -> dict:
            return await admin._handle_schema(model_name)

        @get("/api/{model_name:str}")
        async def model_list(
            request: Request,
            model_name: str,
            page: int = 1,
            per_page: int = 25,
            ordering: str | None = None,
            search: str | None = None,
        ) -> dict:
            return await admin._handle_list(
                model_name,
                request.query_params,
                page,
                per_page,
                ordering,
                search,
            )

        @get("/api/{model_name:str}/options")
        async def model_options(
            model_name: str,
            search: str | None = None,
            limit: int = 25,
            include: str | None = None,
        ) -> list:
            include_list = include.split(",") if include else None
            return await admin._handle_options(
                model_name, search=search, limit=limit, include=include_list
            )

        @get("/api/{model_name:str}/export")
        async def model_export(
            request: Request,
            model_name: str,
            fmt: str = Parameter(default="csv", query="format"),
            ordering: str | None = None,
            search: str | None = None,
            ids: str | None = None,
        ) -> Stream:
            id_list = ids.split(",") if ids else None
            stream, media_type, filename = await admin._handle_export(
                model_name,
                request.query_params,
                fmt,
                ordering,
                search,
                ids=id_list,
            )
            return Stream(
                stream,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @get("/api/{model_name:str}/{pk:str}")
        async def model_get(model_name: str, pk: str) -> dict:
            return await admin._handle_get(model_name, pk)

        @post("/api/{model_name:str}", status_code=201)
        async def model_create(model_name: str, data: dict) -> dict:
            return await admin._handle_create(model_name, data)

        @put("/api/{model_name:str}/{pk:str}")
        async def model_update(model_name: str, pk: str, data: dict) -> dict:
            return await admin._handle_update(model_name, pk, data)

        @delete("/api/{model_name:str}/{pk:str}", status_code=200)
        async def model_delete(model_name: str, pk: str) -> dict:
            return await admin._handle_delete(model_name, pk)

        @post("/api/{model_name:str}/bulk-delete")
        async def model_bulk_delete(model_name: str, data: dict) -> dict:
            return await admin._handle_bulk_delete(model_name, data["ids"])

        @post("/api/{model_name:str}/bulk-update")
        async def model_bulk_update(model_name: str, data: dict) -> dict:
            return await admin._handle_bulk_update(
                model_name, data["ids"], data["data"]
            )

        # -- SPA catch-all -------------------------------------------------

        def _get_mount_prefix(request: Request) -> str:
            root = request.scope.get("root_path", "")
            if root:
                return root
            raw = request.scope.get("raw_path", b"")
            if isinstance(raw, bytes):
                raw = raw.decode("latin-1")
            inner_path = request.scope.get("path", "")
            if raw.rstrip("/").endswith(inner_path.rstrip("/")):
                prefix = raw[: len(raw.rstrip("/")) - len(inner_path.rstrip("/"))]
                if prefix:
                    return prefix.rstrip("/")
            return ""

        def _serve_spa(request: Request, path: str = "") -> Response:
            static_file = admin._resolve_static_file(path.lstrip("/"))
            if static_file is not None:
                return File(path=static_file)
            prefix = _get_mount_prefix(request)
            html = admin._render_index_html(prefix)
            if html is not None:
                return Response(content=html, media_type="text/html")
            return Response(content={"detail": "Frontend not built"}, status_code=404)

        @get("/", name="index")
        async def index(request: Request) -> Response:
            return _serve_spa(request)

        @get("/{path:path}", name="catch_all")
        async def catch_all(request: Request, path: str) -> Response:
            return _serve_spa(request, path)

        return [
            admin_config,
            models_list,
            models_counts,
            model_schema,
            model_list,
            model_options,
            model_export,
            model_get,
            model_create,
            model_update,
            model_delete,
            model_bulk_delete,
            model_bulk_update,
            index,
            catch_all,
        ]
