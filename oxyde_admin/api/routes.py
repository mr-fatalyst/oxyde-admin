from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from oxyde.models import Model


@dataclass
class PaginatedResult:
    items: list[Any]
    total: int
    page: int
    per_page: int


async def list_records(
    model: type[Model],
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
    model: type[Model],
    pk: Any,
) -> Model:
    name, pk_type = _get_pk_field(model)
    return await model.objects.get(**{name: pk_type(pk)})


async def create_record(
    model: type[Model],
    data: dict[str, Any],
) -> Model:
    return await model.objects.create(**data)


async def update_record(
    model: type[Model],
    pk: Any,
    data: dict[str, Any],
    readonly_fields: list[str] | None = None,
) -> Model:
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
    model: type[Model],
    pk: Any,
) -> int:
    name, pk_type = _get_pk_field(model)
    return await model.objects.filter(**{name: pk_type(pk)}).delete()


async def bulk_delete(
    model: type[Model],
    ids: list[Any],
) -> int:
    name, pk_type = _get_pk_field(model)
    typed_ids = [pk_type(i) for i in ids]
    return await model.objects.filter(**{f"{name}__in": typed_ids}).delete()


async def bulk_update(
    model: type[Model],
    ids: list[Any],
    data: dict[str, Any],
    readonly_fields: list[str] | None = None,
) -> int:
    name, pk_type = _get_pk_field(model)
    typed_ids = [pk_type(i) for i in ids]
    blocked = set(readonly_fields or [])
    blocked.add(name)
    clean = {k: v for k, v in data.items() if k not in blocked}
    if not clean:
        return 0
    rows = await model.objects.filter(**{f"{name}__in": typed_ids}).update(**clean)
    return len(rows)


async def get_options(
    model: type[Model],
    display_field: str | None = None,
    *,
    search: str | None = None,
    limit: int = 25,
    include: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return [{value: pk, label: display}] for FK dropdowns."""
    pk_field, pk_type = _get_pk_field(model)
    label_field = display_field or _guess_display_field(model)
    query = model.objects
    if search:
        from oxyde.queries.q import Q

        query = query.filter(Q(**{f"{label_field}__icontains": search}))
    items = await query.limit(limit).all()
    result = [
        {"value": getattr(item, pk_field), "label": getattr(item, label_field)}
        for item in items
    ]
    # Ensure included IDs are in the result
    if include:
        existing = {opt["value"] for opt in result}
        missing = []
        for raw in include:
            try:
                val = pk_type(raw)
            except (ValueError, TypeError):
                continue
            if val not in existing:
                missing.append(val)
        if missing:
            extra = await model.objects.filter(**{f"{pk_field}__in": missing}).all()
            for item in extra:
                result.append(
                    {
                        "value": getattr(item, pk_field),
                        "label": getattr(item, label_field),
                    }
                )
    return result


async def resolve_fk_labels(
    model: type[Model],
    items: list[Any],
    registry: dict,
) -> dict[str, dict]:
    """Resolve FK labels for a page of records.

    Returns ``{column_name: {fk_id: label, ...}, ...}``.
    """
    import asyncio

    from oxyde.models.registry import registered_tables

    fk_fields = {}
    for name, col in model._db_meta.field_metadata.items():
        if col.foreign_key:
            fk_fields[col.db_column] = col

    if not fk_fields:
        return {}

    tables = registered_tables()
    result = {}

    async def _resolve(col_name, col_meta):
        # col_name is the db column (e.g. "author_id") — matches model_dump() keys
        ids = {getattr(item, col_name, None) for item in items}
        ids.discard(None)
        if not ids:
            return
        target_key = col_meta.foreign_key.target
        target = tables.get(target_key)
        if target is None:
            for key, m in tables.items():
                if key.endswith(f".{target_key}") or m.__name__ == target_key:
                    target = m
                    break
        if target is None:
            return
        config = registry.get(target)
        pk_field, pk_type = _get_pk_field(target)
        label_field = (
            config.display_field if config else None
        ) or _guess_display_field(target)
        fk_records = await target.objects.filter(**{f"{pk_field}__in": list(ids)}).all()
        result[col_name] = {
            getattr(r, pk_field): getattr(r, label_field) for r in fk_records
        }

    await asyncio.gather(
        *(_resolve(col_name, col_meta) for col_name, col_meta in fk_fields.items())
    )
    return result


def _get_pk_field(model: type[Model]) -> tuple[str, type]:
    for name, col in model._db_meta.field_metadata.items():
        if col.primary_key:
            return name, col.python_type
    raise ValueError(f"No primary key found for {model.__name__}")


def _guess_display_field(model: type[Model]) -> str:
    """Fallback: first string field, or PK."""
    for name, col in model._db_meta.field_metadata.items():
        if col.python_type is str:
            return name
    return _get_pk_field(model)[0]
