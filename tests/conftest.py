from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from oxyde_admin.adapters.base import AbstractAdapter


class _ColumnMeta:
    """Minimal stand-in for oxyde ColumnMeta."""

    def __init__(
        self,
        name: str,
        *,
        primary_key: bool = False,
        nullable: bool = False,
        unique: bool = False,
        index: bool = False,
        foreign_key=None,
        db_column: str | None = None,
        db_type: str | None = None,
        python_type: type = str,
        max_length: int | None = None,
        db_default=None,
        comment: str | None = None,
    ):
        self.name = name
        self.primary_key = primary_key
        self.nullable = nullable
        self.unique = unique
        self.index = index
        self.foreign_key = foreign_key
        self.db_column = db_column if db_column is not None else name
        self.db_type = db_type
        self.python_type = python_type
        self.max_length = max_length
        self.db_default = db_default
        self.comment = comment


def _make_fk(target: str, target_field: str = "id"):
    return SimpleNamespace(target=target, target_field=target_field)


def _make_objects_mock():
    """Create an AsyncMock QueryManager that supports chaining."""
    qm = AsyncMock()
    qm.filter.return_value = qm
    qm.order_by.return_value = qm
    qm.limit.return_value = qm
    qm.offset.return_value = qm
    return qm


def _make_mock_model(
    name: str,
    table_name: str,
    fields: dict[str, _ColumnMeta],
    schema: dict,
):
    """Build a mock Model class with _db_meta, model_json_schema, objects."""
    meta = SimpleNamespace(table_name=table_name, field_metadata=fields)
    objects = _make_objects_mock()

    cls = type(
        name,
        (),
        {
            "__name__": name,
            "_db_meta": meta,
            "objects": objects,
            "model_json_schema": classmethod(lambda cls_: schema),
            "ensure_field_metadata": classmethod(lambda cls_: None),
        },
    )
    return cls


# ── Mock User ──────────────────────────────────────────────────────────

_USER_FIELDS = {
    "id": _ColumnMeta("id", primary_key=True, python_type=int, db_type="INTEGER"),
    "name": _ColumnMeta(
        "name", python_type=str, max_length=100, db_type="VARCHAR(100)"
    ),
    "email": _ColumnMeta("email", python_type=str, unique=True, db_type="VARCHAR(255)"),
    "is_active": _ColumnMeta(
        "is_active", python_type=bool, db_type="BOOLEAN", db_default=True
    ),
}

_USER_SCHEMA = {
    "title": "MockUser",
    "type": "object",
    "properties": {
        "id": {"title": "Id", "type": "integer"},
        "name": {"title": "Name", "type": "string"},
        "email": {"title": "Email", "type": "string"},
        "is_active": {"title": "Is Active", "type": "boolean"},
    },
    "required": ["name", "email"],
}


@pytest.fixture()
def MockUser():
    return _make_mock_model(
        "MockUser", "users", dict(_USER_FIELDS), _deep_copy_schema(_USER_SCHEMA)
    )


# ── Mock Post ──────────────────────────────────────────────────────────

_POST_FIELDS = {
    "id": _ColumnMeta("id", primary_key=True, python_type=int, db_type="INTEGER"),
    "title": _ColumnMeta(
        "title", python_type=str, max_length=200, db_type="VARCHAR(200)"
    ),
    "author_id": _ColumnMeta(
        "author_id",
        python_type=int,
        foreign_key=_make_fk("User", "id"),
        db_type="INTEGER",
        nullable=True,
        index=True,
    ),
}

_POST_SCHEMA = {
    "title": "MockPost",
    "type": "object",
    "properties": {
        "id": {"title": "Id", "type": "integer"},
        "title": {"title": "Title", "type": "string"},
        "author_id": {"title": "Author Id", "type": "integer"},
    },
    "required": ["title"],
}


@pytest.fixture()
def MockPost():
    return _make_mock_model(
        "MockPost", "posts", dict(_POST_FIELDS), _deep_copy_schema(_POST_SCHEMA)
    )


# ── Mock model with UUID PK ───────────────────────────────────────────

_UUID_FIELDS = {
    "id": _ColumnMeta("id", primary_key=True, python_type=uuid.UUID, db_type="UUID"),
    "label": _ColumnMeta("label", python_type=str),
}

_UUID_SCHEMA = {
    "title": "MockUUID",
    "type": "object",
    "properties": {
        "id": {"title": "Id", "type": "string", "format": "uuid"},
        "label": {"title": "Label", "type": "string"},
    },
}


@pytest.fixture()
def MockUUIDModel():
    return _make_mock_model(
        "MockUUID", "uuids", dict(_UUID_FIELDS), _deep_copy_schema(_UUID_SCHEMA)
    )


# ── Mock model with string PK ─────────────────────────────────────────

_STR_PK_FIELDS = {
    "slug": _ColumnMeta(
        "slug", primary_key=True, python_type=str, db_type="VARCHAR(50)"
    ),
    "value": _ColumnMeta("value", python_type=str),
}


@pytest.fixture()
def MockStrPKModel():
    return _make_mock_model("MockStrPK", "str_pks", dict(_STR_PK_FIELDS), {})


# ── Mock model with UUID FK ───────────────────────────────────────────

_UUID_FK_FIELDS = {
    "id": _ColumnMeta("id", primary_key=True, python_type=int, db_type="INTEGER"),
    "ref_id": _ColumnMeta(
        "ref_id",
        python_type=uuid.UUID,
        foreign_key=_make_fk("MockUUID", "id"),
        db_type="UUID",
    ),
}


@pytest.fixture()
def MockUUIDFKModel():
    return _make_mock_model("MockUUIDFK", "uuid_fk", dict(_UUID_FK_FIELDS), {})


# ── Mock model with no PK ─────────────────────────────────────────────

_NO_PK_FIELDS = {
    "data": _ColumnMeta("data", python_type=str),
}


@pytest.fixture()
def MockNoPKModel():
    return _make_mock_model("MockNoPK", "no_pks", dict(_NO_PK_FIELDS), {})


# ── Adapter fixture ───────────────────────────────────────────────────


class ConcreteAdapter(AbstractAdapter):
    """Minimal concrete subclass for testing base methods."""

    pass


@pytest.fixture()
def adapter():
    return ConcreteAdapter()


# ── Helpers ────────────────────────────────────────────────────────────


def _deep_copy_schema(schema: dict) -> dict:
    """Deep-copy a schema dict so tests don't mutate shared state."""
    import copy

    return copy.deepcopy(schema)


# ── Mock model with special column metadata ────────────────────────────


@pytest.fixture()
def MockCommentModel():
    """Model with comment, db_default, and db_column != name."""
    fields = {
        "id": _ColumnMeta("id", primary_key=True, python_type=int),
        "status": _ColumnMeta(
            "status",
            python_type=str,
            db_column="status_code",
            db_default="active",
            comment="Current status of the record",
        ),
    }
    schema = {
        "title": "MockComment",
        "type": "object",
        "properties": {
            "id": {"title": "Id", "type": "integer"},
            "status": {"title": "Status", "type": "string"},
        },
    }
    return _make_mock_model("MockComment", "comments", fields, schema)
