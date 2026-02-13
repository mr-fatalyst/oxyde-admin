from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from oxyde.models import OxydeModel


async def list_records(
    model: type[OxydeModel],
    *,
    page: int = 1,
    per_page: int = 25,
    ordering: list[str] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = model.objects
    if filters:
        query = query.filter(**filters)

    total = await query.count()

    if ordering:
        query = query.order_by(*ordering)

    offset = (page - 1) * per_page
    items = await query.limit(per_page).offset(offset).all()

    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


async def get_record(
    model: type[OxydeModel],
    pk: Any,
) -> dict[str, Any]:
    pk_field = _get_pk_field(model)
    record = await model.objects.get(**{pk_field: pk})
    return record.model_dump()


async def create_record(
    model: type[OxydeModel],
    data: dict[str, Any],
) -> dict[str, Any]:
    record = await model.objects.create(**data)
    return record.model_dump()


async def update_record(
    model: type[OxydeModel],
    pk: Any,
    data: dict[str, Any],
) -> dict[str, Any]:
    pk_field = _get_pk_field(model)
    record = await model.objects.get(**{pk_field: pk})
    for key, value in data.items():
        setattr(record, key, value)
    await record.save(update_fields=set(data.keys()))
    return record.model_dump()


async def delete_record(
    model: type[OxydeModel],
    pk: Any,
) -> dict[str, Any]:
    pk_field = _get_pk_field(model)
    record = await model.objects.get(**{pk_field: pk})
    await record.delete()
    return {"deleted": True}


def _get_pk_field(model: type[OxydeModel]) -> str:
    for name, col in model._db_meta.field_metadata.items():
        if col.primary_key:
            return name
    raise ValueError(f"No primary key found for {model.__name__}")
