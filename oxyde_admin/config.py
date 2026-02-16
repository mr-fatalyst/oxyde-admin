from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelAdmin:
    list_display: list[str] | None = None
    list_filter: list[str] | None = None
    search_fields: list[str] | None = None
    readonly_fields: list[str] | None = None
    ordering: list[str] | None = None
    display_field: str | None = None
    column_labels: dict[str, str] | None = None
    group: str | None = None
    icon: str | None = None
