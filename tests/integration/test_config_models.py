from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_config(client):
    r = await client.get("/admin/api/config")

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Test Admin"
    assert body["auth_enabled"] is False
    assert body["version"]


async def test_models_list(client):
    r = await client.get("/admin/api/models")

    assert r.status_code == 200
    names = {m["name"] for m in r.json()}
    assert {"authors", "books", "tags", "gadgets"} <= names


async def test_models_counts(client):
    r = await client.get("/admin/api/models/counts")

    assert r.status_code == 200
    counts = r.json()
    assert counts["authors"] == 2
    assert counts["books"] == 3
    assert counts["gadgets"] == 1


async def test_schema(client):
    r = await client.get("/admin/api/books/schema")

    assert r.status_code == 200
    props = r.json()["properties"]
    assert props["id"]["x-db-primary-key"] is True
    # the FK extension lives on the relation property, next to x-db-column
    assert props["author"]["x-db-foreign-key"] == {"model": "authors", "field": "id"}
    assert props["author"]["x-db-column"] == "author_id"
    assert props["keywords"]["x-db-array"] is True
    assert props["tags"]["x-db-m2m"] is True


async def test_unknown_model_is_404(client):
    r = await client.get("/admin/api/nonexistent")

    assert r.status_code == 404
