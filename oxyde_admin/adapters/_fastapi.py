from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
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
    get_options,
)
from oxyde_admin.schema import build_schema

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


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

        self._register_exception_handlers(app)
        self._register_api_routes(app)
        self._register_static(app)

        return app

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
            return {
                "title": self.title,
                "preset": self.preset,
                "primary_color": self.primary_color,
                "surface": self.surface,
            }

        @app.get("/api/models/")
        async def models_list() -> list[dict]:
            result = []
            for model, config in self._registry.items():
                model.ensure_field_metadata()
                meta = model._db_meta
                result.append({
                    "name": meta.table_name,
                    "verbose_name": model.__name__,
                    "field_count": len(meta.field_metadata),
                    "list_display": config.list_display,
                    "ordering": config.ordering,
                    "display_field": config.display_field,
                    "group": config.group,
                    "icon": config.icon,
                })
            return result

        @app.get("/api/{model_name}/schema/", response_model=None)
        async def model_schema(model_name: str):
            model = self._require_model(model_name)
            return build_schema(model)

        @app.get("/api/{model_name}/", response_model=None)
        async def model_list(
            model_name: str,
            page: int = 1,
            per_page: int = 25,
            ordering: str | None = None,
        ):
            model = self._require_model(model_name)
            order_list = ordering.split(",") if ordering else None
            result = await list_records(
                model, page=page, per_page=per_page, ordering=order_list,
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

        @app.get("/api/{model_name}/{pk}/", response_model=None)
        async def model_get(model_name: str, pk: str):
            model = self._require_model(model_name)
            record = await get_record(model, self._cast_pk(model, pk))
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
            data = await request.json()
            record = await update_record(model, self._cast_pk(model, pk), data)
            return record.model_dump()

        @app.delete("/api/{model_name}/{pk}/", response_model=None)
        async def model_delete(model_name: str, pk: str):
            model = self._require_model(model_name)
            count = await delete_record(model, self._cast_pk(model, pk))
            return {"deleted": count}

    def _register_static(self, app: FastAPI) -> None:
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="static")

        index_html = STATIC_DIR / "index.html"

        @app.get("/{path:path}", response_model=None)
        async def catch_all(path: str):
            if index_html.exists():
                return HTMLResponse(index_html.read_text())
            return JSONResponse({"detail": "Frontend not built"}, status_code=404)
