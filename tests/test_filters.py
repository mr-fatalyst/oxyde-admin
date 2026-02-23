from __future__ import annotations

import uuid

from oxyde_admin.adapters.base import AbstractAdapter


class TestExtractFilters:
    def test_extract_filters_no_list_filter(self, MockUser):
        """Without list_filter, no filtering is allowed."""
        result = AbstractAdapter._extract_filters(MockUser, {"name": "alice"})

        assert result is None

    def test_extract_filters_empty_params(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {}, list_filter=["name"])

        assert result is None

    def test_extract_filters_fk_int(self, MockPost):
        result = AbstractAdapter._extract_filters(
            MockPost, {"author_id": "5"}, list_filter=["author_id"]
        )

        assert result == {"author_id": 5}

    def test_extract_filters_fk_string(self, MockPost):
        result = AbstractAdapter._extract_filters(
            MockPost, {"author_id": "abc"}, list_filter=["author_id"]
        )

        assert result == {"author_id": "abc"}

    def test_extract_filters_bool_true(self, MockUser):
        result = AbstractAdapter._extract_filters(
            MockUser, {"is_active": "true"}, list_filter=["is_active"]
        )

        assert result == {"is_active": True}

    def test_extract_filters_bool_false(self, MockUser):
        result = AbstractAdapter._extract_filters(
            MockUser, {"is_active": "false"}, list_filter=["is_active"]
        )

        assert result == {"is_active": False}

    def test_extract_filters_int(self, MockUser):
        result = AbstractAdapter._extract_filters(
            MockUser, {"id": "10"}, list_filter=["id"]
        )

        assert result == {"id": 10}

    def test_extract_filters_str(self, MockUser):
        result = AbstractAdapter._extract_filters(
            MockUser, {"name": "alice"}, list_filter=["name"]
        )

        assert result == {"name__icontains": "alice"}

    def test_extract_filters_fk_uuid(self, MockUUIDFKModel):
        raw = "550e8400-e29b-41d4-a716-446655440000"
        result = AbstractAdapter._extract_filters(
            MockUUIDFKModel, {"ref_id": raw}, list_filter=["ref_id"]
        )

        assert result == {"ref_id": uuid.UUID(raw)}

    def test_extract_filters_skips_empty(self, MockUser):
        result = AbstractAdapter._extract_filters(
            MockUser, {"name": "", "email": None}, list_filter=["name", "email"]
        )

        assert result is None

    def test_extract_filters_ignores_unlisted_field(self, MockUser):
        """Fields not in list_filter are ignored even if present in query."""
        result = AbstractAdapter._extract_filters(
            MockUser, {"name": "alice", "id": "10"}, list_filter=["name"]
        )

        assert result == {"name__icontains": "alice"}

    def test_extract_filters_int_invalid(self, MockUser):
        """Invalid int value is skipped, not 500."""
        result = AbstractAdapter._extract_filters(
            MockUser, {"id": "abc"}, list_filter=["id"]
        )

        assert result is None
