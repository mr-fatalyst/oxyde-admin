from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio

from tests.integration.conftest import _register

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture()
async def small_client(database):
    """Admin with tight limits.

    The logic under test lives in the shared ``AdminSite``, so a single
    adapter is representative for the whole matrix.
    """
    from fastapi import FastAPI

    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Limits", per_page=2, export_chunk_size=1)
    _register(admin)
    outer = FastAPI()
    outer.mount("/admin", admin.app)
    transport = httpx.ASGITransport(app=outer)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_options_limit_capped_at_per_page(small_client):
    r = await small_client.get("/admin/api/books/options", params={"limit": 50})

    assert r.status_code == 200
    assert len(r.json()) == 2  # 3 seeded books, capped at per_page=2


async def test_csv_export_chunks_are_complete(small_client):
    # chunk size 1 → every row comes from its own LIMIT/OFFSET query; without
    # a stable order rows could repeat or go missing between chunks
    r = await small_client.get("/admin/api/books/export", params={"format": "csv"})

    assert r.status_code == 200
    header, *rows = [line for line in r.text.strip().splitlines() if line]
    assert header.startswith("id,")
    ids = [row.split(",")[0] for row in rows]
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert ids == sorted(ids, key=int)  # default PK ordering


async def test_json_export_chunks_are_complete(small_client):
    r = await small_client.get("/admin/api/books/export", params={"format": "json"})

    assert r.status_code == 200
    items = json.loads(r.text)
    ids = [item["id"] for item in items]
    assert len(ids) == 3
    assert len(set(ids)) == 3
