from __future__ import annotations

from conftest import ConcreteAdapter
from oxyde_admin.adapters.base import EXPORT_WARN_THRESHOLD
from oxyde_admin.config import Preset, PrimaryColor, Surface


class TestBuildConfig:
    def test_build_config_fields(self):
        adapter = ConcreteAdapter(
            title="Test Admin",
            preset=Preset.LARA,
            primary_color=PrimaryColor.TEAL,
            surface=Surface.ZINC,
        )
        config = adapter._build_config()

        assert config["title"] == "Test Admin"
        assert config["preset"] == Preset.LARA
        assert config["primary_color"] == PrimaryColor.TEAL
        assert config["surface"] == Surface.ZINC
        assert "version" in config
        assert config["export_warn_threshold"] == EXPORT_WARN_THRESHOLD

    def test_build_config_auth_disabled(self):
        adapter = ConcreteAdapter()
        config = adapter._build_config()

        assert config["auth_enabled"] is False
        assert config["login_url"] is None

    def test_build_config_auth_enabled(self):
        adapter = ConcreteAdapter(
            auth_check=lambda r: True,
            login_url="/login",
        )
        config = adapter._build_config()

        assert config["auth_enabled"] is True
        assert config["login_url"] == "/login"


class TestBuildModelsList:
    def test_build_models_list_includes_readonly(self, MockUser):
        adapter = ConcreteAdapter()
        adapter.register(MockUser, readonly_fields=["id", "email"])
        result = adapter._build_models_list()

        assert len(result) == 1
        assert result[0]["readonly_fields"] == ["id", "email"]

    def test_build_models_list_all_fields(self, MockUser):
        adapter = ConcreteAdapter()
        adapter.register(
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
        result = adapter._build_models_list()
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


class TestResolveModel:
    def test_resolve_model(self, MockUser):
        adapter = ConcreteAdapter()
        adapter.register(MockUser)
        result = adapter._resolve_model("users")

        assert result is MockUser

    def test_resolve_model_not_found(self, MockUser):
        adapter = ConcreteAdapter()
        adapter.register(MockUser)
        result = adapter._resolve_model("nonexistent")

        assert result is None
