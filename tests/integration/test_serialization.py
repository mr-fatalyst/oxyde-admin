"""Regression for B1: UUID / date / datetime fields must serialize in every
adapter — before the ``json_default`` fix Falcon, Sanic and Quart returned 500
for any model with a UUID primary key."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

pytestmark = pytest.mark.asyncio


async def test_uuid_pk_list(client):
    r = await client.get("/admin/api/gadgets")

    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert uuid.UUID(items[0]["id"])


async def test_uuid_pk_get(client):
    listed = (await client.get("/admin/api/gadgets")).json()["items"][0]

    r = await client.get(f"/admin/api/gadgets/{listed['id']}")

    assert r.status_code == 200
    assert r.json()["id"] == listed["id"]
    assert r.json()["name"] == "probe-unit"


async def test_uuid_pk_patch_delete(client):
    # Creating via the API is not covered: create_record strips the PK from the
    # payload and oxyde omits default_factory values from the INSERT, so records
    # with a client-generated UUID PK cannot be created through the admin yet.
    pk = (await client.get("/admin/api/gadgets")).json()["items"][0]["id"]

    r = await client.patch(f"/admin/api/gadgets/{pk}", json={"name": "renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"

    r = await client.delete(f"/admin/api/gadgets/{pk}")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1


async def test_date_datetime_and_array_fields(client):
    r = await client.get("/admin/api/books", params={"search": "dune"})

    dune = r.json()["items"][0]
    assert dune["published"] == "1965-08-01"
    assert datetime.fromisoformat(dune["created_at"])
    assert dune["keywords"] == ["scifi", "desert"]
    assert dune["status"] == "published"
