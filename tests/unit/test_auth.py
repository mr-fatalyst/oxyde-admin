from __future__ import annotations

import pytest

from oxyde_admin.adapters.base import AbstractAdapter
from oxyde_admin.auth import (
    AdminUser,
    AuthProvider,
    AuthRequest,
    _CallbackProvider,
    has_builtin_login,
)
from oxyde_admin.site import AdminSite


def _req(**kwargs) -> AuthRequest:
    defaults = dict(headers={}, cookies={}, path="/api/models", method="GET")
    defaults.update(kwargs)
    return AuthRequest(**defaults)


class TestRequiresAuth:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/api/models", True),
            ("/api/books/1", True),
            ("/api/config", False),
            ("/api/config/", False),
            ("/api/login", False),
            ("/api/login/", False),
            ("/", False),
            ("/assets/index.js", False),
            ("/api", False),
        ],
    )
    def test_paths(self, path, expected):
        assert AbstractAdapter._requires_auth(path) is expected


class TestHasBuiltinLogin:
    def test_without_login_override(self):
        class Provider(AuthProvider):
            async def authenticate(self, request):
                return None

        assert has_builtin_login(Provider()) is False

    def test_with_login_override(self):
        class Provider(AuthProvider):
            async def authenticate(self, request):
                return None

            async def login(self, credentials):
                return "token"

        assert has_builtin_login(Provider()) is True


# TODO(0.7.0): remove — auth_check deprecation tail
class TestLegacyCallback:
    @pytest.mark.asyncio
    async def test_sync_callback_receives_native(self):
        provider = _CallbackProvider(lambda request: request == "native")

        user = await provider.authenticate(_req(native="native"))
        assert isinstance(user, AdminUser)
        assert await provider.authenticate(_req(native="other")) is None

    @pytest.mark.asyncio
    async def test_async_callback(self):
        async def check(request):
            return True

        provider = _CallbackProvider(check)

        assert (await provider.authenticate(_req())).is_authenticated

    def test_admin_site_warns_and_wraps(self):
        with pytest.warns(DeprecationWarning, match="0.7.0"):
            site = AdminSite(auth_check=lambda r: True)

        assert isinstance(site.auth_provider, _CallbackProvider)

    def test_explicit_provider_wins_without_warning(self, recwarn):
        class Provider(AuthProvider):
            async def authenticate(self, request):
                return None

        provider = Provider()
        site = AdminSite(auth_provider=provider)

        assert site.auth_provider is provider
        assert not [w for w in recwarn if w.category is DeprecationWarning]
