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


class Category(OxydeModel):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=100, db_unique=True)
    slug: str = Field(max_length=100, db_unique=True)

    class Meta:
        is_table = True
        table_name = "categories"


class Post(OxydeModel):
    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    content: str = ""
    views: int = 0
    author: Author | None = Field(default=None, db_on_delete="CASCADE")
    category: Category | None = Field(default=None, db_on_delete="SET NULL")

    class Meta:
        is_table = True
        table_name = "posts"


class Comment(OxydeModel):
    id: int | None = Field(default=None, db_pk=True)
    post: Post | None = Field(default=None, db_on_delete="CASCADE")
    author_name: str = Field(max_length=100)
    body: str
    is_approved: bool = False

    class Meta:
        is_table = True
        table_name = "comments"


class Tag(OxydeModel):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=50, db_unique=True)

    class Meta:
        is_table = True
        table_name = "tags"


# --- App ---

app = FastAPI(
    title="Oxyde Admin Example",
    lifespan=db.lifespan(default=DB_URL),
)


# --- Admin ---

admin = FastAPIAdmin()
admin.register(Author, list_display=["name", "email", "is_active"], display_field="name", search_fields=["name", "email"], list_filter=["is_active"], column_labels={"is_active": "Active"}, group="Content", icon="pi pi-users")
admin.register(Category, list_display=["name", "slug"], display_field="name", search_fields=["name"], group="Content", icon="pi pi-folder")
admin.register(Post, list_display=["title", "author_id", "category_id", "views"], search_fields=["title", "content"], list_filter=["author_id", "category_id"], column_labels={"author_id": "Author", "category_id": "Category"}, group="Content", icon="pi pi-file-edit")
admin.register(Comment, list_display=["post_id", "author_name", "is_approved"], search_fields=["author_name", "body"], list_filter=["post_id", "is_approved"], column_labels={"post_id": "Post", "author_name": "Author", "is_approved": "Approved"}, group="Engagement", icon="pi pi-comments")
admin.register(Tag, list_display=["name"], display_field="name", search_fields=["name"])
app.mount("/admin", admin.app)
