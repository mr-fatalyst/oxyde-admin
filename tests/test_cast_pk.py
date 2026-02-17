from __future__ import annotations

import uuid

from conftest import ConcreteAdapter


class TestCastPK:
    def setup_method(self):
        self.adapter = ConcreteAdapter()

    def test_cast_pk_int(self, MockUser):
        result = self.adapter._cast_pk(MockUser, "42")

        assert result == 42
        assert isinstance(result, int)

    def test_cast_pk_uuid(self, MockUUIDModel):
        raw = "550e8400-e29b-41d4-a716-446655440000"
        result = self.adapter._cast_pk(MockUUIDModel, raw)

        assert result == uuid.UUID(raw)
        assert isinstance(result, uuid.UUID)

    def test_cast_pk_string(self, MockStrPKModel):
        result = self.adapter._cast_pk(MockStrPKModel, "my-slug")

        assert result == "my-slug"
        assert isinstance(result, str)

    def test_cast_pk_no_pk_field(self, MockNoPKModel):
        result = self.adapter._cast_pk(MockNoPKModel, "fallback")

        assert result == "fallback"
        assert isinstance(result, str)
