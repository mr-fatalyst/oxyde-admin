from __future__ import annotations

import json

from oxyde_admin.adapters.base import AbstractAdapter


class TestBuildExportData:
    def test_export_json(self):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        content, media_type, filename = AbstractAdapter._build_export_data(
            rows, "users", "json"
        )

        assert media_type == "application/json"
        assert filename == "users.json"
        parsed = json.loads(content)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Alice"

    def test_export_csv(self):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        content, media_type, filename = AbstractAdapter._build_export_data(
            rows, "users", "csv"
        )

        assert media_type == "text/csv"
        assert filename == "users.csv"
        lines = content.strip().splitlines()
        assert lines[0] == "id,name"
        assert lines[1] == "1,Alice"
        assert lines[2] == "2,Bob"

    def test_export_csv_empty(self):
        content, media_type, filename = AbstractAdapter._build_export_data(
            [], "users", "csv"
        )

        assert content == ""
        assert media_type == "text/csv"
        assert filename == "users.csv"

    def test_export_json_empty(self):
        content, media_type, filename = AbstractAdapter._build_export_data(
            [], "users", "json"
        )

        assert media_type == "application/json"
        assert filename == "users.json"
        assert json.loads(content) == []
