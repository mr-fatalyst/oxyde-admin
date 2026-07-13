from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio

from tests.integration.models import Author, Book, Tag

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture()
async def x_client(database):
    """Admin with ``exclude_fields`` configured.

    The logic under test lives in the shared ``AdminSite``, so a single
    adapter is representative for the whole matrix.
    """
    from fastapi import FastAPI

    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Exclude")
    admin.register(Author, display_field="name", exclude_fields=["email"])
    admin.register(Book, search_fields=["title"], exclude_fields=["keywords"])
    admin.register(Tag, display_field="name")
    outer = FastAPI()
    outer.mount("/admin", admin.app)
    transport = httpx.ASGITransport(app=outer)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_excluded_field_absent_from_list_and_detail(x_client):
    r = await x_client.get("/admin/api/authors")
    items = r.json()["items"]
    assert items
    assert all("email" not in item for item in items)

    r = await x_client.get(f"/admin/api/authors/{items[0]['id']}")
    assert "email" not in r.json()


async def test_excluded_field_absent_from_schema(x_client):
    r = await x_client.get("/admin/api/authors/schema")

    schema = r.json()
    assert "email" not in schema["properties"]
    assert "email" not in schema.get("required", [])


async def test_excluded_field_blocked_on_create(x_client):
    r = await x_client.post(
        "/admin/api/books", json={"title": "Sneaky", "keywords": ["hack"]}
    )

    assert r.status_code == 201
    body = r.json()
    assert "keywords" not in body
    assert (await Book.objects.get(id=body["id"])).keywords is None


async def test_excluded_field_blocked_on_update(x_client):
    r = await x_client.get("/admin/api/books", params={"search": "dune"})
    dune = r.json()["items"][0]
    assert "keywords" not in dune

    r = await x_client.patch(
        f"/admin/api/books/{dune['id']}",
        json={"title": "Dune!", "keywords": ["overwritten"]},
    )

    assert r.status_code == 200
    assert r.json()["title"] == "Dune!"
    assert (await Book.objects.get(id=dune["id"])).keywords == ["scifi", "desert"]


async def test_excluded_field_blocked_on_bulk_update(x_client):
    ids = [b["id"] for b in (await x_client.get("/admin/api/books")).json()["items"]]

    r = await x_client.post(
        "/admin/api/books/bulk-update",
        json={"ids": ids, "data": {"keywords": ["mass-hack"]}},
    )

    assert r.status_code == 200
    assert r.json()["updated"] == 0
    books = await Book.objects.filter(id__in=ids).all()
    assert all(b.keywords != ["mass-hack"] for b in books)


async def test_excluded_field_absent_from_export(x_client):
    r = await x_client.get("/admin/api/books/export", params={"format": "csv"})
    assert "keywords" not in r.text.splitlines()[0]

    r = await x_client.get("/admin/api/authors/export", params={"format": "json"})
    items = json.loads(r.text)
    assert items
    assert all("email" not in item for item in items)


async def test_create_with_excluded_required_field_is_422(x_client):
    # email is excluded AND required: creation honestly fails instead of
    # silently accepting a client-supplied value for a hidden field
    r = await x_client.post(
        "/admin/api/authors", json={"name": "X", "email": "hack@x.io"}
    )

    assert r.status_code == 422
