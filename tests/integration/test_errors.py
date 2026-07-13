"""Error contract across the adapter matrix.

Semantic cases (unknown model / missing record / conflict / invalid values)
must return identical codes everywhere. Mechanical cases (garbage query
params) may differ in the exact code where a framework validates natively
(FastAPI 422, Litestar 400), but must always be a 4xx with a ``detail`` body —
never a 500.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_missing_record_is_404(client):
    r = await client.get("/admin/api/authors/999999")

    assert r.status_code == 404
    assert "detail" in r.json()


async def test_invalid_pk_is_404(client):
    r = await client.get("/admin/api/authors/abc")
    assert r.status_code == 404

    r = await client.get("/admin/api/gadgets/not-a-uuid")
    assert r.status_code == 404


async def test_unique_conflict_is_409(client):
    r = await client.post(
        "/admin/api/authors", json={"name": "Dup", "email": "frank@dune.io"}
    )

    assert r.status_code == 409
    assert "detail" in r.json()


async def test_invalid_body_value_is_422(client):
    pk = (await client.get("/admin/api/books")).json()["items"][0]["id"]

    r = await client.patch(f"/admin/api/books/{pk}", json={"published": "not-a-date"})

    assert r.status_code == 422


async def test_garbage_query_params_are_4xx(client):
    r = await client.get("/admin/api/books", params={"page": "abc", "per_page": "x"})

    assert 400 <= r.status_code < 500
    assert "detail" in r.json()


async def test_garbage_options_limit_is_4xx(client):
    r = await client.get("/admin/api/authors/options", params={"limit": "lots"})

    assert 400 <= r.status_code < 500


async def test_bulk_delete_without_ids_is_400(client):
    r = await client.post("/admin/api/books/bulk-delete", json={})

    assert r.status_code == 400
    assert "detail" in r.json()


async def test_bulk_update_without_data_is_400(client):
    r = await client.post("/admin/api/books/bulk-update", json={"ids": [1]})

    assert r.status_code == 400


async def test_bulk_delete_uncastable_id_is_400(client):
    r = await client.post("/admin/api/books/bulk-delete", json={"ids": ["abc"]})

    assert r.status_code == 400
