from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from oxyde.exceptions import NotFoundError, IntegrityError
from oxyde_admin.adapters.base import AbstractAdapter
from oxyde_admin.api.routes import (
    list_records,
    get_record,
    create_record,
    update_record,
    delete_record,
)
from oxyde_admin.schema import build_schema

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class FastAPIAdmin(AbstractAdapter):
    """FastAPI adapter for Oxyde Admin."""

    def __init__(self, prefix: str = "/admin") -> None:
        super().__init__()
        self.prefix = prefix
        self._app: FastAPI | None = None

    @property
    def app(self) -> FastAPI:
        if self._app is None:
            self._app = self._build_app()
        return self._app

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Oxyde Admin", docs_url=None, redoc_url=None)

        self._register_exception_handlers(app)
        self._register_api_routes(app)
        self._register_static(app)

        return app

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
        @app.get("/api/models/")
        async def models_list() -> list[dict]:
            result = []
            for model, _config in self._registry.items():
                meta = model._db_meta
                result.append({
                    "name": meta.table_name,
                    "verbose_name": model.__name__,
                    "field_count": len(meta.field_metadata),
                })
            return result

        @app.get("/api/{model_name}/schema/")
        async def model_schema(model_name: str) -> JSONResponse | dict:
            model = self._resolve_model(model_name)
            if model is None:
                return JSONResponse({"detail": "Model not found"}, status_code=404)
            return build_schema(model)

        @app.get("/api/{model_name}/")
        async def model_list(
            model_name: str,
            page: int = 1,
            per_page: int = 25,
            ordering: str | None = None,
        ) -> JSONResponse | dict:
            model = self._resolve_model(model_name)
            if model is None:
                return JSONResponse({"detail": "Model not found"}, status_code=404)
            order_list = ordering.split(",") if ordering else None
            return await list_records(
                model, page=page, per_page=per_page, ordering=order_list,
            )

        @app.get("/api/{model_name}/{pk}/")
        async def model_get(model_name: str, pk: str) -> JSONResponse | dict:
            model = self._resolve_model(model_name)
            if model is None:
                return JSONResponse({"detail": "Model not found"}, status_code=404)
            return await get_record(model, self._cast_pk(model, pk))

        @app.post("/api/{model_name}/", status_code=201)
        async def model_create(model_name: str, request: Request) -> JSONResponse | dict:
            model = self._resolve_model(model_name)
            if model is None:
                return JSONResponse({"detail": "Model not found"}, status_code=404)
            data = await request.json()
            return await create_record(model, data)

        @app.put("/api/{model_name}/{pk}/")
        async def model_update(
            model_name: str, pk: str, request: Request,
        ) -> JSONResponse | dict:
            model = self._resolve_model(model_name)
            if model is None:
                return JSONResponse({"detail": "Model not found"}, status_code=404)
            data = await request.json()
            return await update_record(model, self._cast_pk(model, pk), data)

        @app.delete("/api/{model_name}/{pk}/")
        async def model_delete(model_name: str, pk: str) -> JSONResponse | dict:
            model = self._resolve_model(model_name)
            if model is None:
                return JSONResponse({"detail": "Model not found"}, status_code=404)
            return await delete_record(model, self._cast_pk(model, pk))

    def _register_static(self, app: FastAPI) -> None:
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="static")

        index_html = STATIC_DIR / "index.html"

        @app.get("/{path:path}")
        async def catch_all(path: str) -> HTMLResponse | JSONResponse:
            if index_html.exists():
                return HTMLResponse(index_html.read_text())
            return JSONResponse({"detail": "Frontend not built"}, status_code=404)
