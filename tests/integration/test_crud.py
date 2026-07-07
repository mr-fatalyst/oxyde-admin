from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_create_get_patch_delete(client):
    r = await client.post(
        "/admin/api/authors", json={"name": "New Author", "email": "new@x.io"}
    )
    assert r.status_code == 201
    pk = r.json()["id"]

    r = await client.get(f"/admin/api/authors/{pk}")
    assert r.status_code == 200
    assert r.json()["name"] == "New Author"

    r = await client.patch(f"/admin/api/authors/{pk}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["email"] == "new@x.io"

    r = await client.delete(f"/admin/api/authors/{pk}")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1

    r = await client.get(f"/admin/api/authors/{pk}")
    assert r.status_code == 404


async def test_list_pagination(client):
    r = await client.get("/admin/api/books", params={"page": 1, "per_page": 2})

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["per_page"] == 2


async def test_list_search(client):
    r = await client.get("/admin/api/books", params={"search": "dune"})

    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Dune"


async def test_list_filter(client):
    r = await client.get("/admin/api/books", params={"status": "published"})

    body = r.json()
    assert body["total"] == 2
    assert {b["title"] for b in body["items"]} == {"Dune", "Neuromancer"}


async def test_list_ordering(client):
    r = await client.get("/admin/api/books", params={"ordering": "-title"})

    titles = [b["title"] for b in r.json()["items"]]
    assert titles == sorted(titles, reverse=True)


async def test_list_fk_labels(client):
    r = await client.get("/admin/api/books")

    fk_labels = r.json()["fk_labels"]
    assert "author_id" in fk_labels
    assert "Frank Herbert" in fk_labels["author_id"].values()


async def test_list_m2m_prefetched(client):
    r = await client.get("/admin/api/books", params={"search": "dune"})

    dune = r.json()["items"][0]
    assert {t["name"] for t in dune["tags"]} == {"scifi", "classic"}


async def test_options(client):
    r = await client.get("/admin/api/authors/options")

    assert r.status_code == 200
    opts = r.json()
    assert {"value", "label"} <= set(opts[0])
    assert "Frank Herbert" in {o["label"] for o in opts}


async def test_m2m_sync_on_update(client):
    r = await client.get("/admin/api/books", params={"search": "neuromancer"})
    book = r.json()["items"][0]
    assert book["tags"] == []

    r = await client.get("/admin/api/tags/options")
    scifi = next(o["value"] for o in r.json() if o["label"] == "scifi")

    r = await client.patch(f"/admin/api/books/{book['id']}", json={"tags": [scifi]})
    assert r.status_code == 200
    assert {t["name"] for t in r.json()["tags"]} == {"scifi"}
