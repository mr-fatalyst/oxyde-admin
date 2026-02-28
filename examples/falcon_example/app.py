import falcon.asgi

from oxyde import db

from models import DB_URL
from auth import LoginResource, MeResource
from routes import PostsResource, PostResource
from admin import admin


class LifespanMiddleware:
    async def process_startup(self, scope, event):
        await db.init(default=DB_URL)

    async def process_shutdown(self, scope, event):
        await db.close()


app = falcon.asgi.App(middleware=[LifespanMiddleware()])

app.add_route("/auth/login", LoginResource())
app.add_route("/auth/me", MeResource())
app.add_route("/api/posts", PostsResource())
app.add_route("/api/posts/{slug}", PostResource())

admin.init_app(app)
