from __future__ import annotations

import datetime
import decimal
import enum
import json
import uuid

import pytest

from oxyde_admin.adapters.base import AbstractAdapter, json_default
from oxyde_admin.exceptions import InvalidParameterError
from oxyde_admin.site import AdminSite
from oxyde_admin.config import Preset, PrimaryColor, Surface


class TestBuildConfig:
    def test_build_config_fields(self):
        site = AdminSite(
            title="Test Admin",
            preset=Preset.LARA,
            primary_color=PrimaryColor.TEAL,
            surface=Surface.ZINC,
        )
        config = site._build_config()

        assert config["title"] == "Test Admin"
        assert config["preset"] == Preset.LARA
        assert config["primary_color"] == PrimaryColor.TEAL
        assert config["surface"] == Surface.ZINC
        assert "version" in config
        assert config["export_chunk_size"] == 10_000
        assert config["max_export_rows"] == 100_000

    def test_build_config_auth_disabled(self):
        site = AdminSite()
        config = site._build_config()

        assert config["auth_enabled"] is False
        assert config["login_url"] is None

    def test_build_config_auth_enabled(self):
        site = AdminSite(
            auth_check=lambda r: True,
            login_url="/login",
        )
        config = site._build_config()

        assert config["auth_enabled"] is True
        assert config["login_url"] == "/login"


class TestBuildModelsList:
    def test_build_models_list_includes_readonly(self, MockUser):
        site = AdminSite()
        site.register(MockUser, readonly_fields=["id", "email"])
        result = site._build_models_list()

        assert len(result) == 1
        assert result[0]["readonly_fields"] == ["id", "email"]

    def test_build_models_list_all_fields(self, MockUser):
        site = AdminSite()
        site.register(
            MockUser,
            list_display=["name"],
            list_filter=["is_active"],
            search_fields=["name"],
            readonly_fields=["id"],
            ordering=["-name"],
            display_field="name",
            column_labels={"name": "Name"},
            exportable=False,
            group="Auth",
            icon="pi pi-users",
        )
        result = site._build_models_list()
        entry = result[0]

        assert entry["name"] == "users"
        assert entry["verbose_name"] == "MockUser"
        assert entry["field_count"] == 4
        assert entry["list_display"] == ["name"]
        assert entry["list_filter"] == ["is_active"]
        assert entry["search_fields"] == ["name"]
        assert entry["readonly_fields"] == ["id"]
        assert entry["ordering"] == ["-name"]
        assert entry["display_field"] == "name"
        assert entry["column_labels"] == {"name": "Name"}
        assert entry["exportable"] is False
        assert entry["group"] == "Auth"
        assert entry["icon"] == "pi pi-users"


class TestRequestParsingHelpers:
    def test_int_param_default_on_missing(self):
        assert AbstractAdapter._int_param({}, "page", 1) == 1
        assert AbstractAdapter._int_param({"page": ""}, "page", 1) == 1

    def test_int_param_parses(self):
        assert AbstractAdapter._int_param({"page": "7"}, "page", 1) == 7

    def test_int_param_garbage_raises(self):
        with pytest.raises(InvalidParameterError, match="page"):
            AbstractAdapter._int_param({"page": "abc"}, "page", 1)

    def test_bulk_ids(self):
        assert AbstractAdapter._bulk_ids({"ids": [1, 2]}) == [1, 2]

    def test_bulk_ids_invalid_shapes_raise(self):
        for body in ({}, {"ids": "1,2"}, None, []):
            with pytest.raises(InvalidParameterError, match="ids"):
                AbstractAdapter._bulk_ids(body)

    def test_bulk_payload(self):
        ids, data = AbstractAdapter._bulk_payload({"ids": [1], "data": {"a": 1}})

        assert ids == [1]
        assert data == {"a": 1}

    def test_bulk_payload_missing_data_raises(self):
        with pytest.raises(InvalidParameterError, match="data"):
            AbstractAdapter._bulk_payload({"ids": [1]})


class TestJsonDefault:
    def test_datetime_date_time(self):
        payload = {
            "dt": datetime.datetime(2026, 7, 6, 12, 30, 15),
            "d": datetime.date(2026, 7, 6),
            "t": datetime.time(12, 30, 15),
        }
        result = json.loads(json.dumps(payload, default=json_default))

        assert result == {
            "dt": "2026-07-06T12:30:15",
            "d": "2026-07-06",
            "t": "12:30:15",
        }

    def test_uuid(self):
        value = uuid.uuid4()
        result = json.loads(json.dumps({"id": value}, default=json_default))

        assert result == {"id": str(value)}

    def test_plain_enum(self):
        class Status(enum.Enum):
            ACTIVE = 1

        result = json.loads(json.dumps({"s": Status.ACTIVE}, default=json_default))

        assert result == {"s": 1}

    def test_str_enum_value(self):
        class Color(enum.Enum):
            RED = "red"

        result = json.loads(json.dumps({"c": Color.RED}, default=json_default))

        assert result == {"c": "red"}

    def test_decimal_preserves_precision(self):
        value = decimal.Decimal("10.010")
        result = json.loads(json.dumps({"price": value}, default=json_default))

        assert result == {"price": "10.010"}

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError, match="not JSON serializable"):
            json.dumps({"x": object()}, default=json_default)


class TestResolveModel:
    def test_resolve_model(self, MockUser):
        site = AdminSite()
        site.register(MockUser)
        result = site._resolve_model("users")

        assert result is MockUser

    def test_resolve_model_not_found(self, MockUser):
        site = AdminSite()
        site.register(MockUser)
        result = site._resolve_model("nonexistent")

        assert result is None
