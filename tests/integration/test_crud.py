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


async def test_m2m_sync_rolls_back_on_failure(client):
    r = await client.get("/admin/api/books", params={"search": "dune"})
    dune = r.json()["items"][0]
    assert {t["name"] for t in dune["tags"]} == {"scifi", "classic"}

    r = await client.get("/admin/api/tags/options")
    scifi = next(o["value"] for o in r.json() if o["label"] == "scifi")

    # duplicate target ids violate UNIQUE(book_id, tag_id) inside the sync;
    # the failed sync must not lose the previously existing links
    r = await client.patch(
        f"/admin/api/books/{dune['id']}", json={"tags": [scifi, scifi]}
    )
    assert r.status_code == 409

    r = await client.get(f"/admin/api/books/{dune['id']}")
    assert {t["name"] for t in r.json()["tags"]} == {"scifi", "classic"}


async def test_bulk_update(client):
    r = await client.get("/admin/api/books", params={"status": "published"})
    ids = [b["id"] for b in r.json()["items"]]
    assert len(ids) == 2

    r = await client.post(
        "/admin/api/books/bulk-update", json={"ids": ids, "data": {"status": "draft"}}
    )
    assert r.status_code == 200
    assert r.json()["updated"] == 2

    r = await client.get("/admin/api/books", params={"status": "draft"})
    assert r.json()["total"] == 3


async def test_bulk_update_validates_values(client):
    r = await client.get("/admin/api/books")
    ids = [b["id"] for b in r.json()["items"]]

    r = await client.post(
        "/admin/api/books/bulk-update",
        json={"ids": ids, "data": {"published": "not-a-date"}},
    )
    assert r.status_code == 422

    r = await client.get("/admin/api/books", params={"search": "dune"})
    assert r.json()["items"][0]["published"] == "1965-08-01"


async def test_bulk_delete(client):
    r = await client.get("/admin/api/books", params={"status": "published"})
    ids = [b["id"] for b in r.json()["items"]]

    r = await client.post("/admin/api/books/bulk-delete", json={"ids": ids})
    assert r.status_code == 200
    assert r.json()["deleted"] == 2

    r = await client.get("/admin/api/books")
    assert r.json()["total"] == 1


async def test_create_rolls_back_on_m2m_failure(client):
    r = await client.get("/admin/api/tags/options")
    scifi = next(o["value"] for o in r.json() if o["label"] == "scifi")

    r = await client.post(
        "/admin/api/books", json={"title": "Ghost Book", "tags": [scifi, scifi]}
    )
    assert r.status_code == 409

    # the record created before the failed sync must not survive
    r = await client.get("/admin/api/books", params={"search": "ghost"})
    assert r.json()["total"] == 0
