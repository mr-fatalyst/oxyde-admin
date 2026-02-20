from __future__ import annotations

import inspect

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

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

    def _require_model(self, model_name: str):
        model = self._resolve_model(model_name)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        return model

    def _register_exception_handlers(self, app: FastAPI) -> None:
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
            model = self._require_model(model_name)
            return build_schema(model)

        @app.get("/api/{model_name}/", response_model=None)
        async def model_list(
            request: Request,
            model_name: str,
            page: int = 1,
            per_page: int = 25,
            ordering: str | None = None,
            search: str | None = None,
        ):
            model = self._require_model(model_name)
            config = self._registry.get(model)
            order_list = ordering.split(",") if ordering else None
            filters = self._extract_filters(model, request.query_params)
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

        @app.get("/api/{model_name}/options/", response_model=None)
        async def model_options(model_name: str):
            model = self._require_model(model_name)
            config = self._registry.get(model)
            display = config.display_field if config else None
            return await get_options(model, display)

        @app.get("/api/{model_name}/export/", response_model=None)
        async def model_export(
            request: Request,
            model_name: str,
            fmt: str = Query("csv", alias="format"),
            ordering: str | None = None,
            search: str | None = None,
        ):
            model = self._require_model(model_name)
            config = self._registry.get(model)
            order_list = ordering.split(",") if ordering else None
            filters = self._extract_filters(model, request.query_params)
            search_flds = config.search_fields if config else None
            total_result = await list_records(
                model,
                page=1,
                per_page=1,
                filters=filters,
                search=search,
                search_fields=search_flds,
            )
            result = await list_records(
                model,
                page=1,
                per_page=total_result.total,
                ordering=order_list,
                filters=filters,
                search=search,
                search_fields=search_flds,
            )
            rows = [item.model_dump() for item in result.items]
            content, media_type, filename = self._build_export_data(
                rows, model_name, fmt
            )
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        @app.get("/api/{model_name}/{pk}/", response_model=None)
        async def model_get(model_name: str, pk: str):
            model = self._require_model(model_name)
            record = await get_record(model, pk)
            return record.model_dump()

        @app.post("/api/{model_name}/", status_code=201, response_model=None)
        async def model_create(model_name: str, request: Request):
            model = self._require_model(model_name)
            data = await request.json()
            record = await create_record(model, data)
            return record.model_dump()

        @app.put("/api/{model_name}/{pk}/", response_model=None)
        async def model_update(model_name: str, pk: str, request: Request):
            model = self._require_model(model_name)
            config = self._registry.get(model)
            data = await request.json()
            record = await update_record(
                model,
                pk,
                data,
                readonly_fields=config.readonly_fields if config else None,
            )
            return record.model_dump()

        @app.delete("/api/{model_name}/{pk}/", response_model=None)
        async def model_delete(model_name: str, pk: str):
            model = self._require_model(model_name)
            count = await delete_record(model, pk)
            return {"deleted": count}

    def _register_static(self, app: FastAPI) -> None:
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="static")

        index_html = STATIC_DIR / "index.html"

        @app.get("/{path:path}", response_model=None)
        async def catch_all(request: Request, path: str):
            if path:
                file_path = (STATIC_DIR / path).resolve()
                if file_path.is_relative_to(STATIC_DIR) and file_path.is_file():
                    return FileResponse(file_path)
            if index_html.exists():
                root = request.scope.get("root_path", "")
                base_href = root.rstrip("/") + "/"
                html = index_html.read_text().replace(
                    "<head>",
                    f'<head><base href="{base_href}">',
                    1,
                )
                return HTMLResponse(html)
            return JSONResponse({"detail": "Frontend not built"}, status_code=404)
