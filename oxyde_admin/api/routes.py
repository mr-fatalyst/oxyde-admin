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
) -> PaginatedResult:
    query = model.objects
    if filters:
        query = query.filter(**filters)

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
    pk_field = _get_pk_field(model)
    return await model.objects.get(**{pk_field: pk})


async def create_record(
    model: type[OxydeModel],
    data: dict[str, Any],
) -> OxydeModel:
    return await model.objects.create(**data)


async def update_record(
    model: type[OxydeModel],
    pk: Any,
    data: dict[str, Any],
) -> OxydeModel:
    pk_field = _get_pk_field(model)
    record = await model.objects.get(**{pk_field: pk})
    for key, value in data.items():
        setattr(record, key, value)
    await record.save(update_fields=set(data.keys()))
    return record


async def delete_record(
    model: type[OxydeModel],
    pk: Any,
) -> int:
    pk_field = _get_pk_field(model)
    return await model.objects.filter(**{pk_field: pk}).delete()


def _get_pk_field(model: type[OxydeModel]) -> str:
    for name, col in model._db_meta.field_metadata.items():
        if col.primary_key:
            return name
    raise ValueError(f"No primary key found for {model.__name__}")
