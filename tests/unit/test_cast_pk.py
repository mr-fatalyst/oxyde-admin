from __future__ import annotations

import uuid

import pytest

from oxyde_admin.api.routes import _get_pk_field


class TestGetPkField:
    def test_int_pk(self, MockUser):
        name, pk_type = _get_pk_field(MockUser)

        assert name == "id"
        assert pk_type is int
        assert pk_type("42") == 42

    def test_uuid_pk(self, MockUUIDModel):
        name, pk_type = _get_pk_field(MockUUIDModel)
        raw = "550e8400-e29b-41d4-a716-446655440000"

        assert name == "id"
        assert pk_type is uuid.UUID
        assert pk_type(raw) == uuid.UUID(raw)

    def test_string_pk(self, MockStrPKModel):
        name, pk_type = _get_pk_field(MockStrPKModel)

        assert name == "slug"
        assert pk_type is str
        assert pk_type("my-slug") == "my-slug"

    def test_no_pk_field(self, MockNoPKModel):
        with pytest.raises(ValueError, match="No primary key"):
            _get_pk_field(MockNoPKModel)
