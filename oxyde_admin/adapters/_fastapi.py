from __future__ import annotations

import inspect

from fastapi import FastAPI, Query, Request
from fastapi.responses import (
    JSONResponse,
    HTMLResponse,
    FileResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from oxyde.exceptions import NotFoundError, IntegrityError
from oxyde_admin.adapters.base import (
    AbstractAdapter,
    ExportNotAllowedError,
    ExportTooLargeError,
    ModelNotFoundError,
    STATIC_DIR,
)


class FastAPIAdmin(AbstractAdapter):
    """FastAPI adapter for Oxyde Admin."""

    def __init__(self, prefix: str = "/admin", **kwargs) -> None:
        super().__init__(**kwargs)
        self.prefix = prefix
        self._app: FastAPI | None = None

    @property
    def app(self) -> FastAPI:
        if self._app is None:
            self._app = self._build_app()
        return self._app

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Oxyde Admin", docs_url=None, redoc_url=None)

        if self.auth_check is not None:
            self._register_auth_middleware(app)

        self._register_exception_handlers(app)
        self._register_api_routes(app)
        self._register_static(app)

        return app

    def _register_auth_middleware(self, app: FastAPI) -> None:
        check = self.auth_check

        async def auth_middleware(request: Request, call_next):
            # Use scope path stripped of root_path (mount prefix)
            root = request.scope.get("root_path", "")
            raw_path = request.scope.get("path", request.url.path)
            path = (
                raw_path[len(root) :]
                if root and raw_path.startswith(root)
                else raw_path
            )
            # Allow static files and config endpoint without auth
            if not path.startswith("/api/") or path == "/api/config/":
                return await call_next(request)
            if inspect.iscoroutinefunction(check):
                allowed = await check(request)
            else:
                allowed = check(request)
            if not allowed:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return await call_next(request)

        app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

    def _register_exception_handlers(self, app: FastAPI) -> None:
        @app.exception_handler(ExportNotAllowedError)
        async def _export_not_allowed(
            request: Request, exc: ExportNotAllowedError
        ) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=403)

        @app.exception_handler(ExportTooLargeError)
        async def _export_too_large(
            request: Request, exc: ExportTooLargeError
        ) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=400)

        @app.exception_handler(ModelNotFoundError)
        async def _model_not_found(
            request: Request, exc: ModelNotFoundError
        ) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=404)

        @app.exception_handler(NotFoundError)
        async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=404)

        @app.exception_handler(IntegrityError)
        async def _integrity(request: Request, exc: IntegrityError) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=409)

        @app.exception_handler(ValidationError)
        async def _validation(request: Request, exc: ValidationError) -> JSONResponse:
            return JSONResponse({"detail": exc.errors()}, status_code=422)

    def _register_api_routes(self, app: FastAPI) -> None:
        @app.get("/api/config/")
        async def admin_config() -> dict:
            return self._build_config()

        @app.get("/api/models/")
        async def models_list() -> list[dict]:
            return self._build_models_list()

        @app.get("/api/models/counts/")
        async def models_counts() -> dict[str, int]:
            return await self._build_models_counts()

        @app.get("/api/{model_name}/schema/", response_model=None)
        async def model_schema(model_name: str):
            return await self._handle_schema(model_name)

        @app.get("/api/{model_name}/", response_model=None)
        async def model_list(
            request: Request,
            model_name: str,
            page: int = 1,
            per_page: int = 25,
            ordering: str | None = None,
            search: str | None = None,
        ):
            return await self._handle_list(
                model_name,
                request.query_params,
                page,
                per_page,
                ordering,
                search,
            )

        @app.get("/api/{model_name}/options/", response_model=None)
        async def model_options(
            model_name: str,
            search: str | None = None,
            limit: int = 25,
            include: str | None = None,
        ):
            include_list = include.split(",") if include else None
            return await self._handle_options(
                model_name, search=search, limit=limit, include=include_list
            )

        @app.get("/api/{model_name}/export/", response_model=None)
        async def model_export(
            request: Request,
            model_name: str,
            fmt: str = Query("csv", alias="format"),
            ordering: str | None = None,
            search: str | None = None,
        ):
            stream, media_type, filename = await self._handle_export(
                model_name,
                request.query_params,
                fmt,
                ordering,
                search,
            )
            return StreamingResponse(
                stream,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @app.get("/api/{model_name}/{pk}/", response_model=None)
        async def model_get(model_name: str, pk: str):
            return await self._handle_get(model_name, pk)

        @app.post("/api/{model_name}/", status_code=201, response_model=None)
        async def model_create(model_name: str, request: Request):
            data = await request.json()
            return await self._handle_create(model_name, data)

        @app.put("/api/{model_name}/{pk}/", response_model=None)
        async def model_update(model_name: str, pk: str, request: Request):
            data = await request.json()
            return await self._handle_update(model_name, pk, data)

        @app.delete("/api/{model_name}/{pk}/", response_model=None)
        async def model_delete(model_name: str, pk: str):
            return await self._handle_delete(model_name, pk)

    def _register_static(self, app: FastAPI) -> None:
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="static")

        @app.get("/{path:path}", response_model=None)
        async def catch_all(request: Request, path: str):
            static_file = self._resolve_static_file(path)
            if static_file is not None:
                return FileResponse(static_file)
            root = request.scope.get("root_path", "")
            html = self._render_index_html(root)
            if html is not None:
                return HTMLResponse(html)
            return JSONResponse({"detail": "Frontend not built"}, status_code=404)
