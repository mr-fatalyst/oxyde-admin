from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Preset(str, Enum):
    AURA = "Aura"
    LARA = "Lara"
    NORA = "Nora"


class PrimaryColor(str, Enum):
    NOIR = "noir"
    EMERALD = "emerald"
    GREEN = "green"
    LIME = "lime"
    ORANGE = "orange"
    AMBER = "amber"
    YELLOW = "yellow"
    TEAL = "teal"
    CYAN = "cyan"
    SKY = "sky"
    BLUE = "blue"
    INDIGO = "indigo"
    VIOLET = "violet"
    PURPLE = "purple"
    FUCHSIA = "fuchsia"
    PINK = "pink"
    ROSE = "rose"


class Surface(str, Enum):
    SLATE = "slate"
    GRAY = "gray"
    ZINC = "zinc"
    NEUTRAL = "neutral"
    STONE = "stone"
    SOHO = "soho"
    VIVA = "viva"
    OCEAN = "ocean"


@dataclass
class ModelAdmin:
    list_display: list[str] | None = None
    list_filter: list[str] | None = None
    search_fields: list[str] | None = None
    readonly_fields: list[str] | None = None
    exclude_fields: list[str] | None = None
    ordering: list[str] | None = None
    display_field: str | None = None
    column_labels: dict[str, str] | None = None
    exportable: bool = True
    group: str | None = None
    icon: str | None = None
