from __future__ import annotations

from typing import Any, get_args, get_origin, TYPE_CHECKING

from oxyde.models import registered_tables

if TYPE_CHECKING:
    from oxyde.models import Model


def build_schema(
    model: type[Model], exclude: list[str] | None = None
) -> dict[str, Any]:
    """Build JSON Schema enriched with ``x-db-*`` extensions from ``_db_meta``.

    Fields listed in ``exclude`` are removed from the schema entirely, so the
    frontend never renders them.
    """
    schema = model.model_json_schema()
    _resolve_enum_refs(schema)
    properties = schema.get("properties", {})
    if exclude:
        for field_name in exclude:
            properties.pop(field_name, None)
        if "required" in schema:
            schema["required"] = [f for f in schema["required"] if f not in exclude]
    fk_table_map = _build_fk_table_map()

    for field_name, col in model._db_meta.field_metadata.items():
        prop = properties.get(field_name)
        if prop is None:
            continue

        if col.primary_key:
            prop["x-db-primary-key"] = True
            prop["x-db-readonly"] = True

        if col.nullable:
            prop["x-db-nullable"] = True

        if col.unique:
            prop["x-db-unique"] = True

        if col.index:
            prop["x-db-index"] = True

        if col.foreign_key is not None:
            fk = col.foreign_key
            prop["x-db-foreign-key"] = {
                "model": fk_table_map.get(fk.target, fk.target),
                "field": fk.target_field,
            }

        if col.db_column != col.name:
            prop["x-db-column"] = col.db_column

        if col.db_type is not None:
            prop["x-db-type"] = col.db_type

        if col.max_length is not None:
            prop["x-db-max-length"] = col.max_length

        if col.db_default is not None:
            prop["x-db-default"] = col.db_default

        if col.comment is not None:
            prop["x-db-comment"] = col.comment

        if get_origin(col.python_type) is list:
            prop["x-db-array"] = True
            args = get_args(col.python_type)
            if args:
                item_type = _PYTHON_TO_JSON_TYPE.get(args[0])
                if item_type:
                    prop["x-db-array-item-type"] = item_type

    # M2M relations
    fk_table_map_rev = {
        model.__name__: model._db_meta.table_name
        for model in registered_tables().values()
        if model._db_meta.table_name
    }
    for rel_name, rel in model._db_meta.relations.items():
        if rel.kind != "many_to_many":
            continue
        prop = properties.get(rel_name)
        if prop is None:
            continue
        prop["x-db-m2m"] = True
        prop["x-db-target"] = fk_table_map_rev.get(rel.target, rel.target)
        prop["x-db-through"] = rel.through

    return schema


def _resolve_enum_refs(schema: dict[str, Any]) -> None:
    """Inline enum ``$ref`` definitions into properties.

    Pydantic emits ``$ref`` for both FK models and Enum types.  The frontend
    skips every ``$ref`` property assuming it is a FK.  By inlining enum
    definitions we make them look like regular typed properties with an
    ``enum`` list so the frontend can render a dropdown.
    """
    defs = schema.get("$defs", {})
    if not defs:
        return
    for prop in schema.get("properties", {}).values():
        # Direct $ref: {"$ref": "#/$defs/GenderEnum"}
        if "$ref" in prop:
            ref_name = prop["$ref"].rsplit("/", 1)[-1]
            definition = defs.get(ref_name, {})
            if "enum" in definition:
                del prop["$ref"]
                prop.update(definition)
            continue
        # anyOf: [{"$ref": "#/$defs/GenderEnum"}, {"type": "null"}]
        if "anyOf" in prop:
            for i, entry in enumerate(prop["anyOf"]):
                if "$ref" in entry:
                    ref_name = entry["$ref"].rsplit("/", 1)[-1]
                    definition = defs.get(ref_name, {})
                    if "enum" in definition:
                        prop["anyOf"][i] = definition


_PYTHON_TO_JSON_TYPE: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _build_fk_table_map() -> dict[str, str]:
    """Map model registry keys to table names for FK resolution."""
    return {
        key: model._db_meta.table_name
        for key, model in registered_tables().items()
        if model._db_meta.table_name
    }
