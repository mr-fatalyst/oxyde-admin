from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from oxyde.models import OxydeModel


@dataclass
class PaginatedResult:
    items: list[Any]
    total: int
    page: int
    per_page: int


async def list_records(
    model: type[OxydeModel],
    *,
    page: int = 1,
    per_page: int = 25,
    ordering: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    search: str | None = None,
    search_fields: list[str] | None = None,
) -> PaginatedResult:
    query = model.objects
    if filters:
        query = query.filter(**filters)

    if search and search_fields:
        from oxyde.queries.q import Q

        conditions = [Q(**{f"{f}__icontains": search}) for f in search_fields]
        q = conditions[0]
        for c in conditions[1:]:
            q = q | c
        query = query.filter(q)

    total = await query.count()

    if ordering:
        query = query.order_by(*ordering)

    offset = (page - 1) * per_page
    items = await query.limit(per_page).offset(offset).all()

    return PaginatedResult(items=items, total=total, page=page, per_page=per_page)


async def get_record(
    model: type[OxydeModel],
    pk: Any,
) -> OxydeModel:
    name, pk_type = _get_pk_field(model)
    return await model.objects.get(**{name: pk_type(pk)})


async def create_record(
    model: type[OxydeModel],
    data: dict[str, Any],
) -> OxydeModel:
    return await model.objects.create(**data)


async def update_record(
    model: type[OxydeModel],
    pk: Any,
    data: dict[str, Any],
    readonly_fields: list[str] | None = None,
) -> OxydeModel:
    name, pk_type = _get_pk_field(model)
    record = await model.objects.get(**{name: pk_type(pk)})
    blocked = set(readonly_fields or [])
    blocked.add(name)
    clean = {k: v for k, v in data.items() if k not in blocked}
    for key, value in clean.items():
        setattr(record, key, value)
    await record.save(update_fields=set(clean.keys()))
    return record


async def delete_record(
    model: type[OxydeModel],
    pk: Any,
) -> int:
    name, pk_type = _get_pk_field(model)
    return await model.objects.filter(**{name: pk_type(pk)}).delete()


async def get_options(
    model: type[OxydeModel],
    display_field: str | None = None,
) -> list[dict[str, Any]]:
    """Return [{value: pk, label: display}] for FK dropdowns."""
    pk_field, _ = _get_pk_field(model)
    label_field = display_field or _guess_display_field(model)
    items = await model.objects.all()
    return [
        {"value": getattr(item, pk_field), "label": getattr(item, label_field)}
        for item in items
    ]


def _get_pk_field(model: type[OxydeModel]) -> tuple[str, type]:
    for name, col in model._db_meta.field_metadata.items():
        if col.primary_key:
            return name, col.python_type
    raise ValueError(f"No primary key found for {model.__name__}")


def _guess_display_field(model: type[OxydeModel]) -> str:
    """Fallback: first string field, or PK."""
    for name, col in model._db_meta.field_metadata.items():
        if col.python_type is str:
            return name
    return _get_pk_field(model)[0]
