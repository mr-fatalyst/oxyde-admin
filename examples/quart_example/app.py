from quart import Quart

from oxyde import db

from models import DB_URL
from auth import bp as auth_bp
from routes import bp as blog_bp
from admin import admin

app = Quart(__name__)

app.register_blueprint(auth_bp)
app.register_blueprint(blog_bp)
admin.init_app(app)


@app.before_serving
async def on_startup():
    await db.init(default=DB_URL)


@app.after_serving
async def on_shutdown():
    await db.close()
