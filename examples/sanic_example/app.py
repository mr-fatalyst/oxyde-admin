from sanic import Sanic

from oxyde import db

from models import DB_URL
from auth import bp as auth_bp
from routes import bp as blog_bp
from admin import admin

app = Sanic("MiniBlog")

app.blueprint(auth_bp)
app.blueprint(blog_bp)
admin.register_exception_handlers(app)
app.blueprint(admin.blueprint)


@app.before_server_start
async def on_startup(app):
    await db.init(default=DB_URL)


@app.after_server_stop
async def on_shutdown(app):
    await db.close()
