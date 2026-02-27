from __future__ import annotations

from unittest.mock import patch

import pytest

from oxyde_admin.site import AdminSite
from oxyde_admin.config import ModelAdmin


class TestRegister:
    def test_register(self, MockUser):
        site = AdminSite()
        site.register(MockUser)

        assert MockUser in site._registry
        assert isinstance(site._registry[MockUser], ModelAdmin)

    def test_register_duplicate_raises(self, MockUser):
        site = AdminSite()
        site.register(MockUser)

        with pytest.raises(ValueError, match="already registered"):
            site.register(MockUser)

    def test_register_with_kwargs(self, MockUser):
        site = AdminSite()
        site.register(
            MockUser,
            list_display=["name", "email"],
            readonly_fields=["id"],
            exportable=False,
            group="Auth",
            icon="pi pi-users",
        )

        config = site._registry[MockUser]
        assert config.list_display == ["name", "email"]
        assert config.readonly_fields == ["id"]
        assert config.exportable is False
        assert config.group == "Auth"
        assert config.icon == "pi pi-users"


class TestRegisterAll:
    @patch("oxyde_admin.site.iter_tables")
    def test_register_all(self, mock_iter, MockUser, MockPost):
        mock_iter.return_value = [MockUser, MockPost]
        site = AdminSite()
        site.register_all()

        assert MockUser in site._registry
        assert MockPost in site._registry

    @patch("oxyde_admin.site.iter_tables")
    def test_register_all_exclude(self, mock_iter, MockUser, MockPost):
        mock_iter.return_value = [MockUser, MockPost]
        site = AdminSite()
        site.register_all(exclude={MockPost})

        assert MockUser in site._registry
        assert MockPost not in site._registry

    @patch("oxyde_admin.site.iter_tables")
    def test_register_all_skips_existing(self, mock_iter, MockUser):
        mock_iter.return_value = [MockUser]
        site = AdminSite()
        site.register(MockUser, list_display=["name"])
        site.register_all()

        assert site._registry[MockUser].list_display == ["name"]


class TestExclude:
    def test_exclude(self, MockUser):
        site = AdminSite()
        site.register(MockUser)
        site.exclude(MockUser)

        assert MockUser not in site._registry

    def test_exclude_missing_noop(self, MockUser):
        site = AdminSite()
        site.exclude(MockUser)  # should not raise


class TestModelsProperty:
    def test_models_property(self, MockUser):
        site = AdminSite()
        site.register(MockUser)
        models = site.models

        assert MockUser in models
        # Verify it's a copy
        models.pop(MockUser)
        assert MockUser in site._registry
