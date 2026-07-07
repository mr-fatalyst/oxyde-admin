from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from oxyde import Field, Model


class BookStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Author(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=100, db_unique=True)

    class Meta:
        is_table = True
        table_name = "authors"


class Tag(Model):
    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=50, db_unique=True)

    class Meta:
        is_table = True
        table_name = "tags"


class Book(Model):
    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    author: Author | None = Field(default=None, db_on_delete="CASCADE")
    status: BookStatus = BookStatus.DRAFT
    published: date | None = Field(default=None, db_nullable=True)
    created_at: datetime | None = Field(default=None, db_default="CURRENT_TIMESTAMP")
    keywords: list[str] | None = Field(default=None, db_nullable=True)
    tags: list[Tag] = Field(default=[], db_m2m=True, db_through="BookTag")

    class Meta:
        is_table = True
        table_name = "books"


class BookTag(Model):
    id: int | None = Field(default=None, db_pk=True)
    book: Book | None = Field(default=None, db_on_delete="CASCADE")
    tag: Tag | None = Field(default=None, db_on_delete="CASCADE")

    class Meta:
        is_table = True
        table_name = "book_tags"
        unique_together = [("book", "tag")]


class Gadget(Model):
    """UUID primary key — the model shape that used to 500 in non-FastAPI adapters."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, db_pk=True)
    name: str = Field(max_length=100)

    class Meta:
        is_table = True
        table_name = "gadgets"
