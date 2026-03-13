from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from oxyde.models import registered_tables

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

    m2m_fields = _get_m2m_fields(model)
    if m2m_fields:
        query = query.prefetch(*m2m_fields)

    offset = (page - 1) * per_page
    items = await query.limit(per_page).offset(offset).all()

    return PaginatedResult(items=items, total=total, page=page, per_page=per_page)


async def get_record(
    model: type[Model],
    pk: Any,
) -> Model:
    name, pk_type = _get_pk_field(model)
    m2m_fields = _get_m2m_fields(model)
    query = model.objects
    if m2m_fields:
        query = query.prefetch(*m2m_fields)
    return await query.filter(**{name: pk_type(pk)}).get()


async def create_record(
    model: type[Model],
    data: dict[str, Any],
    readonly_fields: list[str] | None = None,
    m2m_data: dict[str, list] | None = None,
) -> Model:
    name, _ = _get_pk_field(model)
    blocked = set(readonly_fields or [])
    blocked.add(name)
    clean = {k: v for k, v in data.items() if k not in blocked}
    record = await model.objects.create(**clean)
    if m2m_data:
        await _sync_m2m(model, record, m2m_data)
        m2m_fields = list(m2m_data.keys())
        pk_name = _get_pk_field(model)[0]
        record = (
            await model.objects.prefetch(*m2m_fields)
            .filter(**{pk_name: getattr(record, pk_name)})
            .get()
        )
    return record


async def update_record(
    model: type[Model],
    pk: Any,
    data: dict[str, Any],
    readonly_fields: list[str] | None = None,
    m2m_data: dict[str, list] | None = None,
) -> Model:
    name, pk_type = _get_pk_field(model)
    record = await model.objects.get(**{name: pk_type(pk)})
    blocked = set(readonly_fields or [])
    blocked.add(name)
    clean = {k: v for k, v in data.items() if k not in blocked}
    if clean:
        validated = model.model_validate({**record.model_dump(), **clean})
        for key in clean:
            setattr(record, key, getattr(validated, key))
        await record.save(update_fields=set(clean.keys()))
    if m2m_data:
        await _sync_m2m(model, record, m2m_data)
    m2m_fields = _get_m2m_fields(model)
    if m2m_fields:
        record = (
            await model.objects.prefetch(*m2m_fields)
            .filter(**{name: pk_type(pk)})
            .get()
        )
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
    m2m_data: dict[str, list] | None = None,
) -> int:
    name, pk_type = _get_pk_field(model)
    typed_ids = [pk_type(i) for i in ids]
    blocked = set(readonly_fields or [])
    blocked.add(name)
    clean = {k: v for k, v in data.items() if k not in blocked}
    count = 0
    if clean:
        count = await model.objects.filter(**{f"{name}__in": typed_ids}).update(**clean)
    if m2m_data:
        await _sync_m2m_bulk(model, typed_ids, m2m_data)
        if not count:
            count = len(typed_ids)
    return count


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


def _get_m2m_fields(model: type[Model]) -> list[str]:
    """Return M2M relation names for the model."""
    return [
        name
        for name, rel in model._db_meta.relations.items()
        if rel.kind == "many_to_many"
    ]


def _resolve_model_by_name(name: str) -> type[Model]:
    """Find a model by class name in the registry."""
    tables = registered_tables()
    for key, model in tables.items():
        if key.endswith(f".{name}") or model.__name__ == name:
            return model
    raise ValueError(f"Model '{name}' not found in registry")


async def _sync_m2m_bulk(
    model: type[Model],
    record_pks: list,
    m2m_data: dict[str, list],
) -> None:
    """Sync M2M relations for multiple records: bulk delete + bulk create."""
    for field_name, target_ids in m2m_data.items():
        rel = model._db_meta.relations.get(field_name)
        if rel is None or rel.kind != "many_to_many" or rel.through is None:
            continue

        through_model = _resolve_model_by_name(rel.through)

        source_fk = None
        target_fk = None
        source_key = f".{model.__name__}"
        target_key = f".{rel.target}"

        for meta in through_model._db_meta.field_metadata.values():
            if meta.foreign_key:
                if meta.foreign_key.target.endswith(source_key):
                    source_fk = meta.db_column
                elif meta.foreign_key.target.endswith(target_key):
                    target_fk = meta.db_column

        if source_fk is None or target_fk is None:
            continue

        await through_model.objects.filter(**{f"{source_fk}__in": record_pks}).delete()

        for rpk in record_pks:
            for tid in target_ids:
                await through_model.objects.create(**{source_fk: rpk, target_fk: tid})


async def _sync_m2m(
    model: type[Model],
    record: Any,
    m2m_data: dict[str, list],
) -> None:
    """Sync M2M relations: delete existing junction rows and re-create."""
    pk_name, _ = _get_pk_field(model)
    record_pk = getattr(record, pk_name)

    for field_name, target_ids in m2m_data.items():
        rel = model._db_meta.relations.get(field_name)
        if rel is None or rel.kind != "many_to_many" or rel.through is None:
            continue

        through_model = _resolve_model_by_name(rel.through)

        # Find source_fk and target_fk columns in the through model
        source_fk = None
        target_fk = None
        source_key = f".{model.__name__}"
        target_key = f".{rel.target}"

        for meta in through_model._db_meta.field_metadata.values():
            if meta.foreign_key:
                if meta.foreign_key.target.endswith(source_key):
                    source_fk = meta.db_column
                elif meta.foreign_key.target.endswith(target_key):
                    target_fk = meta.db_column

        if source_fk is None or target_fk is None:
            continue

        # Delete existing junction rows for this record
        await through_model.objects.filter(**{source_fk: record_pk}).delete()

        # Re-create junction rows
        for tid in target_ids:
            await through_model.objects.create(**{source_fk: record_pk, target_fk: tid})
