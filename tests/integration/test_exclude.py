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


@pytest_asyncio.fixture()
async def nested_client(database):
    """Admin where the M2M *target* carries the exclusions, not the source."""
    from fastapi import FastAPI

    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Nested exclude")
    admin.register(Author, display_field="name")
    admin.register(Book, search_fields=["title"], ordering=["id"])
    admin.register(Tag, exclude_fields=["name"])
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


async def test_nested_m2m_hides_target_exclusions_on_read(nested_client):
    r = await nested_client.get("/admin/api/books", params={"search": "dune"})
    dune = r.json()["items"][0]
    assert dune["tags"], "the relation itself must still be serialized"
    assert all("name" not in tag for tag in dune["tags"])
    assert all("id" in tag for tag in dune["tags"])

    r = await nested_client.get(f"/admin/api/books/{dune['id']}")
    assert all("name" not in tag for tag in r.json()["tags"])


async def test_nested_m2m_hides_target_exclusions_on_export(nested_client):
    r = await nested_client.get("/admin/api/books/export", params={"format": "json"})

    items = json.loads(r.text)
    assert any(item["tags"] for item in items)
    assert all("name" not in tag for item in items for tag in item["tags"])


async def test_nested_m2m_hides_target_exclusions_on_write(nested_client):
    tag_ids = [t.id for t in await Tag.objects.all()]

    r = await nested_client.post(
        "/admin/api/books", json={"title": "Fresh", "tags": tag_ids}
    )
    assert r.status_code == 201
    assert len(r.json()["tags"]) == len(tag_ids)
    assert all("name" not in tag for tag in r.json()["tags"])

    r = await nested_client.get("/admin/api/books", params={"search": "neuromancer"})
    book = r.json()["items"][0]
    r = await nested_client.patch(
        f"/admin/api/books/{book['id']}", json={"tags": tag_ids}
    )
    assert r.status_code == 200
    assert all("name" not in tag for tag in r.json()["tags"])


async def test_excluded_relation_drops_the_whole_field(database):
    """An excluded M2M field is dropped outright, not narrowed."""
    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Relation exclude")
    admin.register(Book, exclude_fields=["tags"])
    admin.register(Tag, exclude_fields=["name"])

    assert admin._dump_exclude(Book) == {"tags": True}


async def test_dump_exclude_covers_both_relation_shapes(database):
    """A joined FK nests one object, a prefetched M2M a list of them."""
    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Shapes")
    admin.register(Book)
    admin.register(Author, exclude_fields=["email"])
    admin.register(Tag, exclude_fields=["name"])

    assert admin._dump_exclude(Book) == {
        "author": {"email"},
        "tags": {"__all__": {"name"}},
    }


async def test_joined_fk_hides_target_exclusions(database):
    """``join()`` nests the whole target — its exclusions must survive that."""
    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Joined FK")
    admin.register(Book)
    admin.register(Author, exclude_fields=["email"])

    book = await Book.objects.join("author").filter(title="Dune").get()
    assert book.author.email, "the ORM did populate the nested object"

    dumped = admin._dump(Book, book)

    assert dumped["author"]["name"] == "Frank Herbert"
    assert "email" not in dumped["author"]


async def test_create_with_excluded_required_field_is_422(x_client):
    # email is excluded AND required: creation honestly fails instead of
    # silently accepting a client-supplied value for a hidden field
    r = await x_client.post(
        "/admin/api/authors", json={"name": "X", "email": "hack@x.io"}
    )

    assert r.status_code == 422
