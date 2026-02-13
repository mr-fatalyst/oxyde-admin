from pathlib import Path

from fastapi import FastAPI

from oxyde import OxydeModel, Field, db

from oxyde_admin.adapters import FastAPIAdmin

BASE_DIR = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{BASE_DIR / 'example.db'}"


# --- Models ---

class Author(OxydeModel):
    id: int | None = Field(default=None, db_pk=True)
    name: str
    email: str = Field(db_unique=True)
    is_active: bool = True

    class Meta:
        is_table = True
        table_name = "authors"


class Post(OxydeModel):
    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    content: str = ""
    views: int = 0
    author: Author | None = Field(default=None, db_on_delete="CASCADE")

    class Meta:
        is_table = True
        table_name = "posts"


# --- App ---

app = FastAPI(
    title="Oxyde Admin Example",
    lifespan=db.lifespan(default=DB_URL),
)


# --- Admin ---

admin = FastAPIAdmin()
admin.register(Author, list_display=["name", "email", "is_active"])
admin.register(Post, list_display=["title", "author_id", "views"])
app.mount("/admin", admin.app)
