from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from oxyde_admin import AdminSite

if TYPE_CHECKING:
    from oxyde.models import OxydeModel


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
