from __future__ import annotations

import asyncio
import csv
import io
import json as json_mod
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from oxyde_admin import AdminSite, __version__
from oxyde_admin.config import Preset, PrimaryColor, Surface
from oxyde_admin.api.routes import (
    list_records,
    get_record,
    create_record,
    update_record,
    delete_record,
    get_options,
    resolve_fk_labels,
)
from oxyde_admin.schema import build_schema

if TYPE_CHECKING:
    from oxyde.models import Model

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class ModelNotFoundError(Exception):
    """Raised when a model is not found in the registry."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Model '{name}' not found")


class ExportNotAllowedError(Exception):
    """Raised when export is disabled for a model."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Export is not allowed for '{name}'")


class ExportTooLargeError(Exception):
    """Raised when export exceeds the maximum allowed rows."""

    def __init__(self, total: int, limit: int) -> None:
        self.total = total
        self.limit = limit
        super().__init__(f"Export too large: {total} rows exceed the limit of {limit}")


class AbstractAdapter(AdminSite):
    """Base class for framework-specific adapters."""

    def __init__(
        self,
        *,
        title: str = "Oxyde Admin",
        preset: Preset | str = Preset.AURA,
        primary_color: PrimaryColor | str = PrimaryColor.SKY,
        surface: Surface | str = Surface.SLATE,
        per_page: int = 100,
        export_chunk_size: int = 10_000,
        max_export_rows: int = 100_000,
        auth_check: Callable | None = None,
        login_url: str | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.preset = preset
        self.primary_color = primary_color
        self.surface = surface
        self.per_page = max(1, per_page)
        self.export_chunk_size = max(1, export_chunk_size)
        self.max_export_rows = max(1, max_export_rows)
        self.auth_check = auth_check
        self.login_url = login_url
        self.version = __version__
        self._table_index: dict[str, type[Model]] | None = None

    def _resolve_model(self, name: str) -> type[Model] | None:
        """Find a registered model by its table name."""
        if self._table_index is None:
            self._table_index = {m._db_meta.table_name: m for m in self._registry}
        return self._table_index.get(name)

    def _require_model(self, name: str) -> type[Model]:
        """Find a registered model by table name or raise ModelNotFoundError."""
        model = self._resolve_model(name)
        if model is None:
            raise ModelNotFoundError(name)
        return model

    # ------------------------------------------------------------------
    # Handler methods. Framework-agnostic business logic
    # ------------------------------------------------------------------

    async def _handle_schema(self, model_name: str) -> dict[str, Any]:
        model = self._require_model(model_name)
        return build_schema(model)

    async def _handle_list(
        self,
        model_name: str,
        query_params,
        page: int = 1,
        per_page: int | None = None,
        ordering: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        page = max(1, page)
        per_page = max(1, min(per_page or self.per_page, self.per_page))
        model = self._require_model(model_name)
        config = self._registry.get(model)
        order_list = (
            ordering.split(",") if ordering else (config.ordering if config else None)
        )
        filters = self._extract_filters(
            model, query_params, config.list_filter if config else None
        )
        result = await list_records(
            model,
            page=page,
            per_page=per_page,
            ordering=order_list,
            filters=filters,
            search=search,
            search_fields=config.search_fields if config else None,
        )
        fk_labels = await resolve_fk_labels(model, result.items, self._registry)
        return {
            "items": [item.model_dump() for item in result.items],
            "total": result.total,
            "page": result.page,
            "per_page": result.per_page,
            "fk_labels": fk_labels,
        }

    async def _handle_options(
        self,
        model_name: str,
        search: str | None = None,
        limit: int = 25,
        include: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        model = self._require_model(model_name)
        config = self._registry.get(model)
        display = config.display_field if config else None
        return await get_options(
            model, display, search=search, limit=limit, include=include
        )

    async def _handle_export(
        self,
        model_name: str,
        query_params,
        fmt: str = "csv",
        ordering: str | None = None,
        search: str | None = None,
    ) -> tuple[Any, str, str]:
        """Returns ``(async_generator, media_type, filename)``."""
        model = self._require_model(model_name)
        config = self._registry.get(model)
        if config and not config.exportable:
            raise ExportNotAllowedError(model_name)
        order_list = (
            ordering.split(",") if ordering else (config.ordering if config else None)
        )
        filters = self._extract_filters(
            model, query_params, config.list_filter if config else None
        )
        search_flds = config.search_fields if config else None
        total_result = await list_records(
            model,
            page=1,
            per_page=1,
            filters=filters,
            search=search,
            search_fields=search_flds,
        )
        total = total_result.total
        if total > self.max_export_rows:
            raise ExportTooLargeError(total, self.max_export_rows)

        chunk = self.export_chunk_size
        common = dict(
            ordering=order_list,
            filters=filters,
            search=search,
            search_fields=search_flds,
        )

        if fmt == "json":
            media_type = "application/json"
            filename = f"{model_name}.json"

            async def json_stream():
                yield "["
                first = True
                page = 1
                while True:
                    result = await list_records(
                        model, page=page, per_page=chunk, **common
                    )
                    for item in result.items:
                        row = json_mod.dumps(
                            item.model_dump(), default=str, ensure_ascii=False
                        )
                        if not first:
                            yield ","
                        yield row
                        first = False
                    if len(result.items) < chunk:
                        break
                    page += 1
                yield "]"

            return json_stream(), media_type, filename

        # CSV
        media_type = "text/csv"
        filename = f"{model_name}.csv"

        async def csv_stream():
            header_written = False
            page = 1
            while True:
                result = await list_records(model, page=page, per_page=chunk, **common)
                rows = [item.model_dump() for item in result.items]
                if rows:
                    buf = io.StringIO()
                    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
                    if not header_written:
                        writer.writeheader()
                        header_written = True
                    writer.writerows(rows)
                    yield buf.getvalue()
                if len(result.items) < chunk:
                    break
                page += 1

        return csv_stream(), media_type, filename

    async def _handle_get(self, model_name: str, pk: str) -> dict[str, Any]:
        model = self._require_model(model_name)
        record = await get_record(model, pk)
        return record.model_dump()

    async def _handle_create(
        self, model_name: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        model = self._require_model(model_name)
        record = await create_record(model, data)
        return record.model_dump()

    async def _handle_update(
        self, model_name: str, pk: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        model = self._require_model(model_name)
        config = self._registry.get(model)
        record = await update_record(
            model,
            pk,
            data,
            readonly_fields=config.readonly_fields if config else None,
        )
        return record.model_dump()

    async def _handle_delete(self, model_name: str, pk: str) -> dict[str, Any]:
        model = self._require_model(model_name)
        count = await delete_record(model, pk)
        return {"deleted": count}

    # ------------------------------------------------------------------
    # SPA serving helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_static_file(path: str) -> Path | None:
        """Resolve a URL path to a static file with traversal protection."""
        if not path:
            return None
        file_path = (STATIC_DIR / path).resolve()
        if file_path.is_relative_to(STATIC_DIR) and file_path.is_file():
            return file_path
        return None

    @staticmethod
    def _render_index_html(mount_prefix: str) -> str | None:
        """Return *index.html* with ``<base href>`` injected, or *None*."""
        index_html = STATIC_DIR / "index.html"
        if not index_html.exists():
            return None
        base_href = mount_prefix.rstrip("/") + "/"
        return index_html.read_text().replace(
            "<head>",
            f'<head><base href="{base_href}">',
            1,
        )

    # ------------------------------------------------------------------
    # Config / models list / counts
    # ------------------------------------------------------------------

    def _build_config(self) -> dict:
        """Build config endpoint data."""
        return {
            "title": self.title,
            "preset": self.preset,
            "primary_color": self.primary_color,
            "surface": self.surface,
            "version": self.version,
            "auth_enabled": self.auth_check is not None,
            "login_url": self.login_url,
            "per_page": self.per_page,
            "export_chunk_size": self.export_chunk_size,
            "max_export_rows": self.max_export_rows,
        }

    def _build_models_list(self) -> list[dict]:
        """Build models list data."""
        result = []
        for model, config in self._registry.items():
            meta = model._db_meta
            result.append(
                {
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
                    "readonly_fields": config.readonly_fields,
                    "group": config.group,
                    "icon": config.icon,
                }
            )
        return result

    async def _build_models_counts(self) -> dict[str, int]:
        """Build model counts."""
        models = list(self._registry)
        counts = await asyncio.gather(*(m.objects.count() for m in models))
        return {m._db_meta.table_name: c for m, c in zip(models, counts)}

    @staticmethod
    def _extract_filters(
        model, query_params, list_filter: list[str] | None = None
    ) -> dict | None:
        """Extract filter values from query params for filterable columns."""
        if not list_filter:
            return None
        allowed = set(list_filter)
        col_map = {}
        for name, col in model._db_meta.field_metadata.items():
            if name not in allowed and col.db_column not in allowed:
                continue
            col_map[col.db_column] = (name, col)

        filters = {}
        for col_name, (field_name, meta) in col_map.items():
            val = query_params.get(col_name)
            if val is None or val == "":
                continue
            if meta.foreign_key:
                try:
                    filters[field_name] = meta.python_type(val)
                except (ValueError, TypeError):
                    filters[field_name] = val
            elif meta.python_type is bool:
                filters[field_name] = val.lower() == "true"
            elif meta.python_type is int:
                try:
                    filters[field_name] = int(val)
                except (ValueError, TypeError):
                    continue
            elif meta.python_type is str:
                filters[f"{field_name}__icontains"] = val
            else:
                filters[field_name] = val
        return filters or None
