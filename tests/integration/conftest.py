from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import uuid
from datetime import date

import httpx
import pytest
import pytest_asyncio

from oxyde import db, execute_raw

from tests.integration.models import Author, Book, BookTag, Gadget, Tag

DDL = [
    """
    CREATE TABLE IF NOT EXISTS authors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE,
        status TEXT NOT NULL DEFAULT 'draft',
        published DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        keywords TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS book_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
        tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
        UNIQUE(book_id, tag_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gadgets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """,
]


async def _seed() -> None:
    frank = await Author.objects.create(name="Frank Herbert", email="frank@dune.io")
    william = await Author.objects.create(name="William Gibson", email="wg@sprawl.io")

    scifi = await Tag.objects.create(name="scifi")
    classic = await Tag.objects.create(name="classic")

    dune = await Book.objects.create(
        title="Dune",
        author_id=frank.id,
        status="published",
        published=date(1965, 8, 1),
        keywords=["scifi", "desert"],
    )
    await Book.objects.create(
        title="Neuromancer",
        author_id=william.id,
        status="published",
    )
    await Book.objects.create(title="Unfinished Draft", author_id=william.id)

    await BookTag.objects.create(book_id=dune.id, tag_id=scifi.id)
    await BookTag.objects.create(book_id=dune.id, tag_id=classic.id)

    # id is passed explicitly: oxyde only includes explicitly-set fields in the
    # INSERT, so a default_factory value never reaches the query (NULL PK).
    await Gadget.objects.create(id=uuid.uuid4(), name="probe-unit")


@pytest_asyncio.fixture()
async def database(tmp_path):
    await db.init(default=f"sqlite:///{tmp_path}/test.db")
    for stmt in DDL:
        await execute_raw(stmt)
    await _seed()
    yield
    await db.close()


# ---------------------------------------------------------------------------
# Adapter matrix
# ---------------------------------------------------------------------------


def _register(admin) -> None:
    admin.register(
        Author,
        display_field="name",
        search_fields=["name", "email"],
        list_filter=["name"],
    )
    admin.register(
        Book,
        search_fields=["title"],
        list_filter=["status", "author_id"],
        ordering=["id"],
    )
    admin.register(Tag, display_field="name")
    admin.register(Gadget)


def build_fastapi(**admin_kwargs):
    from fastapi import FastAPI

    from oxyde_admin import FastAPIAdmin

    admin = FastAPIAdmin(title="Test Admin", **admin_kwargs)
    _register(admin)
    outer = FastAPI()
    outer.mount("/admin", admin.app)
    return outer


def build_litestar(**admin_kwargs):
    from litestar import Litestar, asgi

    from oxyde_admin import LitestarAdmin

    admin = LitestarAdmin(title="Test Admin", **admin_kwargs)
    _register(admin)
    return Litestar(
        route_handlers=[asgi(path="/admin", is_mount=True, copy_scope=True)(admin.app)]
    )


def build_sanic(**admin_kwargs):
    import sanic

    from oxyde_admin import SanicAdmin

    sanic.Sanic.test_mode = True
    admin = SanicAdmin(title="Test Admin", prefix="/admin", **admin_kwargs)
    _register(admin)
    app = sanic.Sanic("TestApp")
    admin.register_exception_handlers(app)
    app.blueprint(admin.blueprint)
    return app


def build_quart(**admin_kwargs):
    from quart import Quart

    from oxyde_admin import QuartAdmin

    admin = QuartAdmin(title="Test Admin", prefix="/admin", **admin_kwargs)
    _register(admin)
    app = Quart(__name__)
    admin.init_app(app)
    return app


def build_falcon(**admin_kwargs):
    import falcon.asgi

    from oxyde_admin import FalconAdmin

    admin = FalconAdmin(title="Test Admin", prefix="/admin", **admin_kwargs)
    _register(admin)
    app = falcon.asgi.App()
    admin.init_app(app)
    return app


# (builder, needs_lifespan): Sanic initializes app.loop during ASGI lifespan
# startup, which httpx.ASGITransport does not run — drive it manually.
ADAPTERS = {
    "falcon": (build_falcon, False),
    "fastapi": (build_fastapi, False),
    "litestar": (build_litestar, False),
    "quart": (build_quart, False),
    "sanic": (build_sanic, True),
}


class LifespanManager:
    """Minimal ASGI lifespan runner for transports that skip the protocol."""

    def __init__(self, app) -> None:
        self.app = app
        self._startup_done = asyncio.Event()
        self._shutdown_done = asyncio.Event()
        self._messages: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def _receive(self):
        return await self._messages.get()

    async def _send(self, message) -> None:
        if message["type"] == "lifespan.startup.complete":
            self._startup_done.set()
        elif message["type"] == "lifespan.shutdown.complete":
            self._shutdown_done.set()

    async def __aenter__(self):
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}}
        self._task = asyncio.ensure_future(self.app(scope, self._receive, self._send))
        await self._messages.put({"type": "lifespan.startup"})
        await asyncio.wait_for(self._startup_done.wait(), timeout=5)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._messages.put({"type": "lifespan.shutdown"})
        await asyncio.wait_for(self._shutdown_done.wait(), timeout=5)
        if self._task is not None:
            await self._task


@asynccontextmanager
async def admin_client(adapter: str, **admin_kwargs):
    """HTTP client over an admin app mounted at /admin."""
    build, needs_lifespan = ADAPTERS[adapter]
    app = build(**admin_kwargs)
    transport = httpx.ASGITransport(app=app)
    if needs_lifespan:
        async with LifespanManager(app):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as c:
                yield c
    else:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture(params=sorted(ADAPTERS))
def adapter(request):
    """Framework name; every dependent test runs once per adapter."""
    return request.param


@pytest_asyncio.fixture()
async def client(adapter, database):
    async with admin_client(adapter) as c:
        yield c
