from __future__ import annotations

import inspect
from typing import Any

from litestar import Litestar, Request, get, post, put, delete
from litestar.params import Parameter
from litestar.static_files import StaticFilesConfig
from litestar.openapi import OpenAPIConfig
from litestar.response import Response, File, Stream
from litestar.types import ASGIApp, Receive, Scope, Send
from pydantic import ValidationError

from oxyde.exceptions import NotFoundError, IntegrityError
from oxyde_admin.adapters.base import (
    AbstractAdapter,
    ExportNotAllowedError,
    ExportTooLargeError,
    ModelNotFoundError,
    STATIC_DIR,
)


class LitestarAdmin(AbstractAdapter):
    """Litestar adapter for Oxyde Admin."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._app: Litestar | None = None

    @property
    def app(self) -> Litestar:
        if self._app is None:
            self._app = self._build_app()
        return self._app

    def _build_app(self) -> Litestar:
        handlers = self._build_route_handlers()

        middleware = []
        if self.auth_check is not None:
            middleware.append(self._create_auth_middleware())

        exception_handlers: dict[type[Exception], Any] = {
            ExportNotAllowedError: self._exc_export_not_allowed,
            ExportTooLargeError: self._exc_export_too_large,
            ModelNotFoundError: self._exc_model_not_found,
            NotFoundError: self._exc_not_found,
            IntegrityError: self._exc_integrity,
            ValidationError: self._exc_validation,
        }

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
                # Allow static files and config endpoint without auth
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

    @staticmethod
    async def _exc_export_not_allowed(
        request: Request, exc: ExportNotAllowedError
    ) -> Response:
        return Response(content={"detail": str(exc)}, status_code=403)

    @staticmethod
    async def _exc_export_too_large(
        request: Request, exc: ExportTooLargeError
    ) -> Response:
        return Response(content={"detail": str(exc)}, status_code=400)

    @staticmethod
    async def _exc_model_not_found(
        request: Request, exc: ModelNotFoundError
    ) -> Response:
        return Response(content={"detail": str(exc)}, status_code=404)

    @staticmethod
    async def _exc_not_found(request: Request, exc: NotFoundError) -> Response:
        return Response(content={"detail": str(exc)}, status_code=404)

    @staticmethod
    async def _exc_integrity(request: Request, exc: IntegrityError) -> Response:
        return Response(content={"detail": str(exc)}, status_code=409)

    @staticmethod
    async def _exc_validation(request: Request, exc: ValidationError) -> Response:
        return Response(content={"detail": exc.errors()}, status_code=422)

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    def _build_route_handlers(self) -> list:
        admin = self

        @get("/api/config/")
        async def admin_config() -> dict:
            return admin._build_config()

        @get("/api/models/")
        async def models_list() -> list[dict]:
            return admin._build_models_list()

        @get("/api/models/counts/")
        async def models_counts() -> dict[str, int]:
            return await admin._build_models_counts()

        @get("/api/{model_name:str}/schema/")
        async def model_schema(model_name: str) -> dict:
            return await admin._handle_schema(model_name)

        @get("/api/{model_name:str}/")
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

        @get("/api/{model_name:str}/options/")
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

        @get("/api/{model_name:str}/export/")
        async def model_export(
            request: Request,
            model_name: str,
            fmt: str = Parameter(default="csv", query="format"),
            ordering: str | None = None,
            search: str | None = None,
        ) -> Stream:
            stream, media_type, filename = await admin._handle_export(
                model_name,
                request.query_params,
                fmt,
                ordering,
                search,
            )
            return Stream(
                stream,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @get("/api/{model_name:str}/{pk:str}/")
        async def model_get(model_name: str, pk: str) -> dict:
            return await admin._handle_get(model_name, pk)

        @post("/api/{model_name:str}/", status_code=201)
        async def model_create(model_name: str, data: dict) -> dict:
            return await admin._handle_create(model_name, data)

        @put("/api/{model_name:str}/{pk:str}/")
        async def model_update(model_name: str, pk: str, data: dict) -> dict:
            return await admin._handle_update(model_name, pk, data)

        @delete("/api/{model_name:str}/{pk:str}/", status_code=200)
        async def model_delete(model_name: str, pk: str) -> dict:
            return await admin._handle_delete(model_name, pk)

        # -- SPA catch-all -------------------------------------------------

        def _get_mount_prefix(request: Request) -> str:
            """Derive mount prefix from scope.

            Litestar ASGI mounts strip the prefix from ``path`` but keep it in
            ``raw_path``.  ``root_path`` is only set by the ASGI server (e.g.
            uvicorn ``--root-path``), not by the framework mount, so we fall
            back to comparing raw vs stripped path.
            """
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
            index,
            catch_all,
        ]
