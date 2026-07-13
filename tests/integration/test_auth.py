from __future__ import annotations

import pytest
import pytest_asyncio

from oxyde_admin import AdminUser, AuthProvider

from tests.integration.conftest import admin_client

pytestmark = pytest.mark.asyncio


class TokenProvider(AuthProvider):
    async def authenticate(self, request):
        if request.headers.get("authorization") == "Bearer good-token":
            return AdminUser(id="1", name="Admin")
        return None

    async def login(self, credentials):
        if (
            credentials.email == "admin@x.io"
            and credentials.password.get_secret_value() == "s3cret"
        ):
            return "good-token"
        return None


@pytest_asyncio.fixture()
async def auth_client(adapter, database):
    async with admin_client(adapter, auth_provider=TokenProvider()) as c:
        yield c


async def test_api_requires_auth(auth_client):
    r = await auth_client.get("/admin/api/models")

    assert r.status_code == 401
    assert r.json() == {"detail": "Unauthorized"}


async def test_config_is_exempt_and_exposes_auth_block(auth_client):
    r = await auth_client.get("/admin/api/config")

    assert r.status_code == 200
    auth = r.json()["auth"]
    assert auth["enabled"] is True
    assert auth["builtin_login"] is True
    props = auth["credentials_schema"]["properties"]
    assert set(props) == {"email", "password"}
    assert props["password"]["format"] == "password"


async def test_login_flow(auth_client):
    r = await auth_client.post(
        "/admin/api/login", json={"email": "admin@x.io", "password": "s3cret"}
    )
    assert r.status_code == 200
    token = r.json()["token"]

    r = await auth_client.get(
        "/admin/api/models", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200


async def test_login_wrong_credentials_is_401(auth_client):
    r = await auth_client.post(
        "/admin/api/login", json={"email": "admin@x.io", "password": "wrong"}
    )

    assert r.status_code == 401


async def test_login_invalid_body_is_422(auth_client):
    # 422 (and not the gate's 401) proves /api/login itself is exempt
    r = await auth_client.post("/admin/api/login", json={})

    assert r.status_code == 422


async def test_spa_is_not_gated(auth_client):
    r = await auth_client.get("/admin/", follow_redirects=True)

    assert r.status_code != 401


async def test_login_404_without_builtin_login(adapter, database):
    class NoLoginProvider(AuthProvider):
        async def authenticate(self, request):
            return None

    async with admin_client(adapter, auth_provider=NoLoginProvider()) as c:
        r = await c.post("/admin/api/login", json={"email": "a", "password": "b"})
        assert r.status_code == 404

        r = await c.get("/admin/api/config")
        assert r.json()["auth"]["builtin_login"] is False
        assert r.json()["auth"]["credentials_schema"] is None


# TODO(0.7.0): remove — auth_check deprecation tail
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
async def test_legacy_auth_check_denies(adapter, database):
    async with admin_client(adapter, auth_check=lambda request: False) as c:
        r = await c.get("/admin/api/models")
        assert r.status_code == 401

        r = await c.get("/admin/api/config")
        assert r.status_code == 200


# TODO(0.7.0): remove — auth_check deprecation tail
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
async def test_legacy_async_auth_check_receives_native_request(adapter, database):
    async def check(request):
        # the legacy contract passes the framework-native request object
        return request is not None

    async with admin_client(adapter, auth_check=check) as c:
        r = await c.get("/admin/api/models")
        assert r.status_code == 200
