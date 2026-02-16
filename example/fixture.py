import asyncio
import random

from oxyde import db, execute_raw

from app import DB_URL, Author, Post, Category, Comment, Tag


AUTHORS = [
    ("Alice Johnson", "alice@example.com", True),
    ("Bob Smith", "bob@example.com", False),
    ("Carol White", "carol@example.com", True),
    ("Dave Brown", "dave@example.com", True),
    ("Eve Davis", "eve@example.com", False),
    ("Frank Miller", "frank@example.com", True),
    ("Grace Wilson", "grace@example.com", True),
    ("Hank Moore", "hank@example.com", False),
    ("Ivy Taylor", "ivy@example.com", True),
    ("Jack Anderson", "jack@example.com", True),
    ("Karen Thomas", "karen@example.com", True),
    ("Leo Martinez", "leo@example.com", False),
]

CATEGORIES = [
    ("Tutorials", "tutorials"),
    ("Guides", "guides"),
    ("Quick Tips", "quick-tips"),
    ("Release Notes", "release-notes"),
    ("Community", "community"),
]

TAGS = [
    "python", "async", "orm", "sqlite", "postgresql",
    "fastapi", "pydantic", "testing", "deployment", "docker",
    "performance", "security", "beginner", "advanced", "tutorial",
]

TITLES = [
    "Getting Started with Oxyde",
    "Advanced Query Patterns",
    "Database Migrations Guide",
    "Working with Foreign Keys",
    "Async Python Best Practices",
    "Building REST APIs",
    "Authentication Deep Dive",
    "Deploying to Production",
    "Performance Tuning Tips",
    "Testing Strategies",
    "Error Handling Patterns",
    "Caching with Redis",
    "WebSocket Integration",
    "File Upload Handling",
    "Pagination Done Right",
    "Full-Text Search",
    "Background Tasks",
    "Rate Limiting",
    "Logging and Monitoring",
    "CI/CD Pipeline Setup",
    "Docker Compose Workflow",
    "Type Safety in Python",
    "Pydantic v2 Migration",
    "SQLite vs PostgreSQL",
    "Data Validation Patterns",
    "API Versioning",
    "GraphQL vs REST",
    "Event-Driven Architecture",
    "Microservices with FastAPI",
    "Security Best Practices",
]

EXTRA_TITLES = [
    "Quick Tip: F-Expressions",
    "Quick Tip: Q Objects",
    "Quick Tip: Select Related",
    "Quick Tip: Bulk Operations",
    "Quick Tip: Raw SQL",
    "Quick Tip: Transactions",
    "Quick Tip: Model Hooks",
    "Quick Tip: Custom Managers",
    "Quick Tip: Aggregation",
    "Quick Tip: Subqueries",
    "Tutorial: Blog App Part 1",
    "Tutorial: Blog App Part 2",
    "Tutorial: Blog App Part 3",
    "Tutorial: Blog App Part 4",
    "Tutorial: Blog App Part 5",
    "Tutorial: Chat App Part 1",
    "Tutorial: Chat App Part 2",
    "Tutorial: Chat App Part 3",
    "Tutorial: Todo App",
    "Tutorial: E-Commerce App",
    "Release Notes v0.1.0",
    "Release Notes v0.2.0",
    "Release Notes v0.3.0",
    "Roadmap 2025",
    "Community Highlights",
    "Contributor Guide",
    "FAQ",
    "Troubleshooting Common Errors",
    "Changelog",
    "Benchmarks Update",
]

COMMENT_BODIES = [
    "Great article, thanks for sharing!",
    "This helped me solve a tricky bug.",
    "Could you elaborate on the second section?",
    "I've been looking for this, very useful.",
    "Nice writeup! One small correction though...",
    "Would love to see a follow-up on this topic.",
    "Clear and concise, bookmarked.",
    "How does this compare to Django's approach?",
    "Worked perfectly, thanks!",
    "I ran into an issue with step 3, any ideas?",
    "Excellent explanation of a complex topic.",
    "This should be in the official docs.",
    "Thanks, saved me hours of debugging.",
    "Any plans to support MySQL as well?",
    "The code examples are really helpful.",
]

COMMENTER_NAMES = [
    "anonymous", "dev_jane", "rustfan42", "py_newbie",
    "dbadmin", "webdev_mike", "sarah_codes", "linux_user",
    "async_lover", "sql_guru", "fastapi_fan", "beginner123",
]


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
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE
        )
    """)
    await execute_raw("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            views INTEGER NOT NULL DEFAULT 0,
            author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL
        )
    """)
    await execute_raw("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
            author_name TEXT NOT NULL,
            body TEXT NOT NULL,
            is_approved BOOLEAN NOT NULL DEFAULT 0
        )
    """)
    await execute_raw("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    count = await Author.objects.count()
    if count > 0:
        print(f"Already has {count} authors, skipping")
        await db.close()
        return

    random.seed(42)

    # Authors
    authors = []
    for name, email, is_active in AUTHORS:
        author = await Author.objects.create(name=name, email=email, is_active=is_active)
        authors.append(author)
    active_authors = [a for a in authors if a.is_active]

    # Categories
    categories = []
    for name, slug in CATEGORIES:
        cat = await Category.objects.create(name=name, slug=slug)
        categories.append(cat)

    # Tags
    tags = []
    for name in TAGS:
        tag = await Tag.objects.create(name=name)
        tags.append(tag)

    # Posts
    posts = []
    for i, title in enumerate(TITLES):
        author = random.choice(active_authors)
        category = random.choice(categories)
        views = random.randint(0, 5000)
        content = f"Content for article #{i + 1}: {title}. " * random.randint(1, 4)
        post = await Post.objects.create(
            title=title,
            content=content.strip(),
            views=views,
            author_id=author.id,
            category_id=category.id,
        )
        posts.append(post)

    for title in EXTRA_TITLES:
        author = random.choice(authors)
        category = random.choice(categories)
        views = random.randint(0, 2000)
        post = await Post.objects.create(
            title=title,
            content=f"Content for {title}.",
            views=views,
            author_id=author.id,
            category_id=category.id,
        )
        posts.append(post)

    # Comments (spread across posts, ~120 total)
    for post in posts:
        num_comments = random.randint(0, 5)
        for _ in range(num_comments):
            await Comment.objects.create(
                post_id=post.id,
                author_name=random.choice(COMMENTER_NAMES),
                body=random.choice(COMMENT_BODIES),
                is_approved=random.random() > 0.3,
            )

    total_posts = await Post.objects.count()
    total_comments = await Comment.objects.count()
    print(f"Seeded {len(authors)} authors, {len(categories)} categories, "
          f"{total_posts} posts, {total_comments} comments, {len(tags)} tags")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
