from __future__ import annotations

from unittest.mock import patch

from oxyde_admin.schema import build_schema


@patch("oxyde_admin.schema.registered_tables", return_value={})
class TestBuildSchema:
    def test_build_schema_primary_key(self, _mock_rt, MockUser):
        schema = build_schema(MockUser)
        prop = schema["properties"]["id"]

        assert prop["x-db-primary-key"] is True
        assert prop["x-db-readonly"] is True

    def test_build_schema_nullable(self, _mock_rt, MockPost):
        schema = build_schema(MockPost)
        prop = schema["properties"]["author_id"]

        assert prop["x-db-nullable"] is True

    def test_build_schema_unique(self, _mock_rt, MockUser):
        schema = build_schema(MockUser)
        prop = schema["properties"]["email"]

        assert prop["x-db-unique"] is True

    def test_build_schema_index(self, _mock_rt, MockPost):
        schema = build_schema(MockPost)
        prop = schema["properties"]["author_id"]

        assert prop["x-db-index"] is True

    def test_build_schema_foreign_key(self, _mock_rt, MockPost):
        schema = build_schema(MockPost)
        prop = schema["properties"]["author_id"]

        assert "x-db-foreign-key" in prop
        assert prop["x-db-foreign-key"]["field"] == "id"

    def test_build_schema_foreign_key_with_table_map(self, mock_rt, MockUser, MockPost):
        mock_rt.return_value = {"User": MockUser}
        schema = build_schema(MockPost)
        prop = schema["properties"]["author_id"]

        assert prop["x-db-foreign-key"]["model"] == "users"

    def test_build_schema_db_column(self, _mock_rt, MockCommentModel):
        schema = build_schema(MockCommentModel)
        prop = schema["properties"]["status"]

        assert prop["x-db-column"] == "status_code"

    def test_build_schema_db_type(self, _mock_rt, MockUser):
        schema = build_schema(MockUser)

        assert schema["properties"]["id"]["x-db-type"] == "INTEGER"
        assert schema["properties"]["name"]["x-db-type"] == "VARCHAR(100)"

    def test_build_schema_max_length(self, _mock_rt, MockUser):
        schema = build_schema(MockUser)

        assert schema["properties"]["name"]["x-db-max-length"] == 100

    def test_build_schema_db_default(self, _mock_rt, MockUser):
        schema = build_schema(MockUser)
        prop = schema["properties"]["is_active"]

        assert prop["x-db-default"] is True

    def test_build_schema_comment(self, _mock_rt, MockCommentModel):
        schema = build_schema(MockCommentModel)
        prop = schema["properties"]["status"]

        assert prop["x-db-comment"] == "Current status of the record"

    def test_build_schema_array(self, _mock_rt, MockArrayModel):
        schema = build_schema(MockArrayModel)
        prop = schema["properties"]["keywords"]

        assert prop["x-db-array"] is True
        assert prop["x-db-array-item-type"] == "string"

    def test_build_schema_array_not_on_regular_fields(self, _mock_rt, MockUser):
        schema = build_schema(MockUser)

        for prop in schema["properties"].values():
            assert "x-db-array" not in prop


@patch("oxyde_admin.schema.registered_tables", return_value={})
class TestExcludeFields:
    def test_exclude_removes_property_and_required(self, _mock_rt, MockUser):
        schema = build_schema(MockUser, exclude=["email"])

        assert "email" not in schema["properties"]
        assert "email" not in schema.get("required", [])
        assert "name" in schema["properties"]

    def test_exclude_unknown_field_is_noop(self, _mock_rt, MockUser):
        schema = build_schema(MockUser, exclude=["nonexistent"])

        assert set(schema["properties"]) == {"id", "name", "email", "is_active"}
