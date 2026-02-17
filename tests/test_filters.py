from __future__ import annotations

from oxyde_admin.adapters.base import AbstractAdapter


class TestExtractFilters:
    def test_extract_filters_empty(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {})

        assert result is None

    def test_extract_filters_fk_int(self, MockPost):
        result = AbstractAdapter._extract_filters(MockPost, {"author_id": "5"})

        assert result == {"author_id": 5}

    def test_extract_filters_fk_string(self, MockPost):
        result = AbstractAdapter._extract_filters(MockPost, {"author_id": "abc"})

        assert result == {"author_id": "abc"}

    def test_extract_filters_bool_true(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {"is_active": "true"})

        assert result == {"is_active": True}

    def test_extract_filters_bool_false(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {"is_active": "false"})

        assert result == {"is_active": False}

    def test_extract_filters_int(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {"id": "10"})

        assert result == {"id": 10}

    def test_extract_filters_str(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {"name": "alice"})

        assert result == {"name__icontains": "alice"}

    def test_extract_filters_skips_empty(self, MockUser):
        result = AbstractAdapter._extract_filters(MockUser, {"name": "", "email": None})

        assert result is None
