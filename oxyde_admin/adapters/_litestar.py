from __future__ import annotations

import inspect
from typing import Any

from litestar import Litestar, Request, get, post, put, delete
from litestar.static_files import StaticFilesConfig
from litestar.exceptions import NotFoundException
from litestar.openapi import OpenAPIConfig
from litestar.response import Response, File
from litestar.types import ASGIApp, Receive, Scope, Send
from pydantic import ValidationError

from oxyde.exceptions import NotFoundError, IntegrityError
from oxyde_admin.adapters.base import AbstractAdapter, STATIC_DIR
from oxyde_admin.api.routes import (
    list_records,
    get_record,
    create_record,
    update_record,
    delete_record,
    get_options,
)
from oxyde_admin.schema import build_schema


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
            NotFoundError: self._handle_not_found,
            IntegrityError: self._handle_integrity,
            ValidationError: self._handle_validation,
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
                title="Oxyde Admin", version="0.1.0", path=None
            ),
        )

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

    def _require_model(self, model_name: str):
        model = self._resolve_model(model_name)
        if model is None:
            raise NotFoundException(detail="Model not found")
        return model

    @staticmethod
    async def _handle_not_found(request: Request, exc: NotFoundError) -> Response:
        return Response(content={"detail": str(exc)}, status_code=404)

    @staticmethod
    async def _handle_integrity(request: Request, exc: IntegrityError) -> Response:
        return Response(content={"detail": str(exc)}, status_code=409)

    @staticmethod
    async def _handle_validation(request: Request, exc: ValidationError) -> Response:
        return Response(content={"detail": exc.errors()}, status_code=422)

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
            model = admin._require_model(model_name)
            return build_schema(model)

        @get("/api/{model_name:str}/")
        async def model_list(
            request: Request,
            model_name: str,
            page: int = 1,
            per_page: int = 25,
            ordering: str | None = None,
            search: str | None = None,
        ) -> dict:
            model = admin._require_model(model_name)
            config = admin._registry.get(model)
            order_list = ordering.split(",") if ordering else None
            filters = admin._extract_filters(model, request.query_params)
            result = await list_records(
                model,
                page=page,
                per_page=per_page,
                ordering=order_list,
                filters=filters,
                search=search,
                search_fields=config.search_fields if config else None,
            )
            return {
                "items": [item.model_dump() for item in result.items],
                "total": result.total,
                "page": result.page,
                "per_page": result.per_page,
            }

        @get("/api/{model_name:str}/options/")
        async def model_options(model_name: str) -> list:
            model = admin._require_model(model_name)
            config = admin._registry.get(model)
            display = config.display_field if config else None
            return await get_options(model, display)

        @get("/api/{model_name:str}/export/")
        async def model_export(
            request: Request,
            model_name: str,
            format: str = "csv",
            ordering: str | None = None,
            search: str | None = None,
        ) -> Response:
            model = admin._require_model(model_name)
            config = admin._registry.get(model)
            order_list = ordering.split(",") if ordering else None
            filters = admin._extract_filters(model, request.query_params)
            result = await list_records(
                model,
                page=1,
                per_page=10000,
                ordering=order_list,
                filters=filters,
                search=search,
                search_fields=config.search_fields if config else None,
            )
            rows = [item.model_dump() for item in result.items]
            content, media_type, filename = admin._build_export_data(
                rows, model_name, format
            )
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @get("/api/{model_name:str}/{pk:str}/")
        async def model_get(model_name: str, pk: str) -> dict:
            model = admin._require_model(model_name)
            record = await get_record(model, admin._cast_pk(model, pk))
            return record.model_dump()

        @post("/api/{model_name:str}/", status_code=201)
        async def model_create(model_name: str, data: dict) -> dict:
            model = admin._require_model(model_name)
            record = await create_record(model, data)
            return record.model_dump()

        @put("/api/{model_name:str}/{pk:str}/")
        async def model_update(model_name: str, pk: str, data: dict) -> dict:
            model = admin._require_model(model_name)
            record = await update_record(model, admin._cast_pk(model, pk), data)
            return record.model_dump()

        @delete("/api/{model_name:str}/{pk:str}/", status_code=200)
        async def model_delete(model_name: str, pk: str) -> dict:
            model = admin._require_model(model_name)
            count = await delete_record(model, admin._cast_pk(model, pk))
            return {"deleted": count}

        index_html = STATIC_DIR / "index.html"

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
            path = path.lstrip("/")
            if path:
                file_path = (STATIC_DIR / path).resolve()
                if file_path.is_relative_to(STATIC_DIR) and file_path.is_file():
                    return File(path=file_path)
            if index_html.exists():
                prefix = _get_mount_prefix(request)
                base_href = prefix.rstrip("/") + "/"
                html = index_html.read_text().replace(
                    "<head>",
                    f'<head><base href="{base_href}">',
                    1,
                )
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
