from pathlib import Path

from oxyde import Model, Field

BASE_DIR = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{BASE_DIR / 'example.db'}"


class User(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str
    email: str = Field(db_unique=True)
    password_hash: str = ""
    is_admin: bool = False

    class Meta:
        is_table = True
        table_name = "users"


class Category(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=100, db_unique=True)
    slug: str = Field(max_length=100, db_unique=True)

    class Meta:
        is_table = True
        table_name = "categories"


class Post(Model):
    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    slug: str = Field(max_length=200, db_unique=True)
    content: str = ""
    views: int = 0
    author: User | None = Field(default=None, db_on_delete="CASCADE")
    category: Category | None = Field(default=None, db_on_delete="SET NULL")
    is_published: bool = True

    class Meta:
        is_table = True
        table_name = "posts"


class Comment(Model):
    id: int | None = Field(default=None, db_pk=True)
    post: Post | None = Field(default=None, db_on_delete="CASCADE")
    author_name: str = Field(max_length=100)
    body: str
    is_approved: bool = False

    class Meta:
        is_table = True
        table_name = "comments"


class Tag(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=50, db_unique=True)

    class Meta:
        is_table = True
        table_name = "tags"
