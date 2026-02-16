from fastapi import FastAPI
from oxyde import db

from models import DB_URL
from auth import router as auth_router
from routes import router as blog_router
from admin import admin

app = FastAPI(
    title="Mini Blog",
    lifespan=db.lifespan(default=DB_URL),
)

app.include_router(auth_router)
app.include_router(blog_router)
app.mount("/admin", admin.app)
