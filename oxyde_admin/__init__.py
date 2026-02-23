from __future__ import annotations

from typing import TYPE_CHECKING

from oxyde.models import iter_tables

from oxyde_admin.config import ModelAdmin, Preset, PrimaryColor, Surface
from oxyde_admin.schema import build_schema

if TYPE_CHECKING:
    from oxyde.models import Model


class AdminSite:
    def __init__(self) -> None:
        self._registry: dict[type[Model], ModelAdmin] = {}

    def register(self, model: type[Model], **kwargs) -> None:
        if model in self._registry:
            raise ValueError(f"{model.__name__} is already registered")
        self._registry[model] = ModelAdmin(**kwargs)

    def register_all(self, *, exclude: set[type[Model]] | None = None) -> None:
        exclude = exclude or set()
        for model in iter_tables():
            if model not in exclude and model not in self._registry:
                self._registry[model] = ModelAdmin()

    def exclude(self, model: type[Model]) -> None:
        self._registry.pop(model, None)

    @property
    def models(self) -> dict[type[Model], ModelAdmin]:
        return dict(self._registry)


__all__ = [
    "AdminSite",
    "ModelAdmin",
    "Preset",
    "PrimaryColor",
    "Surface",
    "build_schema",
]
