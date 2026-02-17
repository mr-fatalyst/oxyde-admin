from __future__ import annotations

import csv
import importlib.metadata
import io
import json as json_mod
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from oxyde_admin import AdminSite

if TYPE_CHECKING:
    from oxyde.models import OxydeModel

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class AbstractAdapter(AdminSite):
    """Base class for framework-specific adapters."""

    def __init__(
        self,
        *,
        title: str = "Oxyde Admin",
        preset: str = "Aura",
        primary_color: str = "sky",
        surface: str = "slate",
        auth_check: Callable | None = None,
        login_url: str | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.preset = preset
        self.primary_color = primary_color
        self.surface = surface
        self.auth_check = auth_check
        self.login_url = login_url

    def _resolve_model(self, name: str) -> type[OxydeModel] | None:
        """Find a registered model by its table name."""
        for model in self._registry:
            if model._db_meta.table_name == name:
                return model
        return None

    def _cast_pk(self, model: type[OxydeModel], pk: str) -> Any:
        """Cast a PK string from URL to the field's Python type."""
        for col in model._db_meta.field_metadata.values():
            if col.primary_key:
                if col.python_type is int:
                    return int(pk)
                return pk
        return pk

    def _build_config(self) -> dict:
        """Build config endpoint data."""
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
            "auth_enabled": self.auth_check is not None,
            "login_url": self.login_url,
        }

    def _build_models_list(self) -> list[dict]:
        """Build models list data."""
        result = []
        for model, config in self._registry.items():
            model.ensure_field_metadata()
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
                    "group": config.group,
                    "icon": config.icon,
                }
            )
        return result

    async def _build_models_counts(self) -> dict[str, int]:
        """Build model counts."""
        result = {}
        for model in self._registry:
            count = await model.objects.count()
            result[model._db_meta.table_name] = count
        return result

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

    @staticmethod
    def _build_export_data(
        rows: list[dict], model_name: str, fmt: str
    ) -> tuple[str, str, str]:
        """Build export data. Returns (content, media_type, filename)."""
        if fmt == "json":
            content = json_mod.dumps(rows, default=str, ensure_ascii=False)
            return content, "application/json", f"{model_name}.json"

        # CSV
        if not rows:
            return "", "text/csv", f"{model_name}.csv"
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue(), "text/csv", f"{model_name}.csv"
