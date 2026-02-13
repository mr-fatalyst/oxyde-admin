import asyncio

from oxyde import db, execute_raw

from app import DB_URL, Author, Post


async def main():
    await db.init(default=DB_URL)

    await execute_raw("""
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT 1
        )
    """)
    await execute_raw("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            views INTEGER NOT NULL DEFAULT 0,
            author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE
        )
    """)

    count = await Author.objects.count()
    if count == 0:
        alice = await Author.objects.create(name="Alice", email="alice@example.com")
        bob = await Author.objects.create(name="Bob", email="bob@example.com", is_active=False)
        await Post.objects.create(title="Hello World", content="First post", author_id=alice.id)
        await Post.objects.create(title="Oxyde ORM", content="ORM guide", views=42, author_id=alice.id)
        await Post.objects.create(title="Draft", content="WIP", author_id=bob.id)
        print("Seeded 2 authors + 3 posts")
    else:
        print(f"Already has {count} authors, skipping")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
