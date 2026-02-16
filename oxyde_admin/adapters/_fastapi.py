from __future__ import annotations

import csv
import importlib.metadata
import inspect
import io
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

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

        if self.auth_check is not None:
            self._register_auth_middleware(app)

        self._register_exception_handlers(app)
        self._register_api_routes(app)
        self._register_static(app)

        return app

    def _register_auth_middleware(self, app: FastAPI) -> None:
        check = self.auth_check

        async def auth_middleware(request: Request, call_next):
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

    @staticmethod
    def _extract_filters(model, query_params) -> dict | None:
        """Extract filter values from query params for all model columns."""
        col_map = {}
        for name, col in model._db_meta.field_metadata.items():
            col_map[col.db_column] = (name, col)

        filters = {}
        for col_name, (field_name, meta) in col_map.items():
            val = query_params.get(col_name)
            if val is None or val == "":
                continue
            if meta.foreign_key:
                try:
                    filters[field_name] = int(val)
                except ValueError:
                    filters[field_name] = val
            elif meta.python_type is bool:
                filters[field_name] = val.lower() == "true"
            elif meta.python_type is int:
                filters[field_name] = int(val)
            elif meta.python_type is str:
                filters[f"{field_name}__icontains"] = val
            else:
                filters[field_name] = val
        return filters or None

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
            try:
                version = importlib.metadata.version("oxyde-admin")
            except importlib.metadata.PackageNotFoundError:
                version = "dev"
            return {
                "title": self.title,
                "preset": self.preset,
                "primary_color": self.primary_color,
                "surface": self.surface,
                "version": version,
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
                    "list_filter": config.list_filter,
                    "column_labels": config.column_labels,
                    "exportable": config.exportable,
                    "search_fields": config.search_fields,
                    "group": config.group,
                    "icon": config.icon,
                })
            return result

        @app.get("/api/models/counts/")
        async def models_counts() -> dict[str, int]:
            result = {}
            for model in self._registry:
                count = await model.objects.count()
                result[model._db_meta.table_name] = count
            return result

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
            format: str = "csv",
            ordering: str | None = None,
            search: str | None = None,
        ):
            model = self._require_model(model_name)
            config = self._registry.get(model)
            order_list = ordering.split(",") if ordering else None
            filters = self._extract_filters(model, request.query_params)
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

            if format == "json":
                import json as json_mod

                content = json_mod.dumps(rows, default=str, ensure_ascii=False)
                return Response(
                    content=content,
                    media_type="application/json",
                    headers={
                        "Content-Disposition": f'attachment; filename="{model_name}.json"',
                    },
                )

            # CSV
            if not rows:
                return Response(
                    content="",
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f'attachment; filename="{model_name}.csv"',
                    },
                )
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
            return Response(
                content=buf.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{model_name}.csv"',
                },
            )

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
        async def catch_all(request: Request, path: str):
            if index_html.exists():
                root = request.scope.get("root_path", "")
                base_href = root.rstrip("/") + "/"
                html = index_html.read_text().replace(
                    "<head>", f'<head><base href="{base_href}">', 1,
                )
                return HTMLResponse(html)
            return JSONResponse({"detail": "Frontend not built"}, status_code=404)
