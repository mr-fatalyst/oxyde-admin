from __future__ import annotations

from typing import TYPE_CHECKING

from oxyde.models import iter_tables

from oxyde_admin.config import ModelAdmin, Preset, PrimaryColor, Surface
from oxyde_admin.schema import build_schema

if TYPE_CHECKING:
    from oxyde.models import OxydeModel


class AdminSite:
    def __init__(self) -> None:
        self._registry: dict[type[OxydeModel], ModelAdmin] = {}

    def register(self, model: type[OxydeModel], **kwargs) -> None:
        if model in self._registry:
            raise ValueError(f"{model.__name__} is already registered")
        self._registry[model] = ModelAdmin(**kwargs)

    def register_all(self, *, exclude: set[type[OxydeModel]] | None = None) -> None:
        exclude = exclude or set()
        for model in iter_tables():
            if model not in exclude and model not in self._registry:
                self._registry[model] = ModelAdmin()

    def exclude(self, model: type[OxydeModel]) -> None:
        self._registry.pop(model, None)

    @property
    def models(self) -> dict[type[OxydeModel], ModelAdmin]:
        return dict(self._registry)


__all__ = [
    "AdminSite",
    "ModelAdmin",
    "Preset",
    "PrimaryColor",
    "Surface",
    "build_schema",
]
