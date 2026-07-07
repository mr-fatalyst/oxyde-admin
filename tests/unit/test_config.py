from __future__ import annotations

from oxyde_admin.config import ModelAdmin, Preset, PrimaryColor, Surface


class TestModelAdmin:
    def test_model_admin_defaults(self):
        cfg = ModelAdmin()

        assert cfg.list_display is None
        assert cfg.list_filter is None
        assert cfg.search_fields is None
        assert cfg.readonly_fields is None
        assert cfg.ordering is None
        assert cfg.display_field is None
        assert cfg.column_labels is None
        assert cfg.exportable is True
        assert cfg.group is None
        assert cfg.icon is None

    def test_model_admin_custom(self):
        cfg = ModelAdmin(
            list_display=["name"],
            list_filter=["is_active"],
            search_fields=["name", "email"],
            readonly_fields=["id"],
            ordering=["-name"],
            display_field="name",
            column_labels={"name": "Full Name"},
            exportable=False,
            group="Auth",
            icon="pi pi-users",
        )

        assert cfg.list_display == ["name"]
        assert cfg.list_filter == ["is_active"]
        assert cfg.search_fields == ["name", "email"]
        assert cfg.readonly_fields == ["id"]
        assert cfg.ordering == ["-name"]
        assert cfg.display_field == "name"
        assert cfg.column_labels == {"name": "Full Name"}
        assert cfg.exportable is False
        assert cfg.group == "Auth"
        assert cfg.icon == "pi pi-users"


class TestPreset:
    def test_preset_values(self):
        assert Preset.AURA.value == "Aura"
        assert Preset.LARA.value == "Lara"
        assert Preset.NORA.value == "Nora"
        assert len(Preset) == 3


class TestPrimaryColor:
    def test_primary_color_values(self):
        expected = {
            "NOIR": "noir",
            "EMERALD": "emerald",
            "GREEN": "green",
            "LIME": "lime",
            "ORANGE": "orange",
            "AMBER": "amber",
            "YELLOW": "yellow",
            "TEAL": "teal",
            "CYAN": "cyan",
            "SKY": "sky",
            "BLUE": "blue",
            "INDIGO": "indigo",
            "VIOLET": "violet",
            "PURPLE": "purple",
            "FUCHSIA": "fuchsia",
            "PINK": "pink",
            "ROSE": "rose",
        }
        for name, value in expected.items():
            assert PrimaryColor[name].value == value
        assert len(PrimaryColor) == len(expected)


class TestSurface:
    def test_surface_values(self):
        expected = {
            "SLATE": "slate",
            "GRAY": "gray",
            "ZINC": "zinc",
            "NEUTRAL": "neutral",
            "STONE": "stone",
            "SOHO": "soho",
            "VIVA": "viva",
            "OCEAN": "ocean",
        }
        for name, value in expected.items():
            assert Surface[name].value == value
        assert len(Surface) == len(expected)
