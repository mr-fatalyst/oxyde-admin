from datetime import datetime
from enum import Enum
from pathlib import Path

from oxyde import Model, Field


class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


BASE_DIR = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{BASE_DIR / 'example.db'}"


class User(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=100, db_unique=True)
    password_hash: str = Field(default="", max_length=255)
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


class Tag(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=50, db_unique=True)

    class Meta:
        is_table = True
        table_name = "tags"


class Post(Model):
    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    slug: str = Field(max_length=200, db_unique=True)
    content: str = ""
    views: int = 0
    author: User | None = Field(default=None, db_on_delete="CASCADE")
    category: Category | None = Field(default=None, db_on_delete="SET NULL")
    status: PostStatus = PostStatus.PUBLISHED
    created_at: datetime | None = Field(default=None, db_default="CURRENT_TIMESTAMP")
    updated_at: datetime | None = Field(default=None, db_default="CURRENT_TIMESTAMP")
    keywords: list[str] | None = Field(default=None, db_nullable=True)
    tags: list[Tag] = Field(default=[], db_m2m=True, db_through="PostTag")

    class Meta:
        is_table = True
        table_name = "posts"


class Comment(Model):
    id: int | None = Field(default=None, db_pk=True)
    post: Post | None = Field(default=None, db_on_delete="CASCADE")
    author_name: str = Field(max_length=100)
    body: str
    is_approved: bool = False
    created_at: datetime | None = Field(default=None, db_default="CURRENT_TIMESTAMP")

    class Meta:
        is_table = True
        table_name = "comments"


class PostTag(Model):
    id: int | None = Field(default=None, db_pk=True)
    post: Post | None = Field(default=None, db_on_delete="CASCADE")
    tag: Tag | None = Field(default=None, db_on_delete="CASCADE")

    class Meta:
        is_table = True
        table_name = "post_tags"
        unique_together = [("post", "tag")]
