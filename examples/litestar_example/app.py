from litestar import Litestar, asgi

from oxyde import db

from models import DB_URL
from routes import list_posts_handler, get_post_handler
from admin import admin

admin_mount = asgi(path="/admin", is_mount=True)(admin.app)


async def on_startup() -> None:
    await db.init(default=DB_URL)


async def on_shutdown() -> None:
    await db.close()


app = Litestar(
    route_handlers=[
        list_posts_handler,
        get_post_handler,
        admin_mount,
    ],
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
)
