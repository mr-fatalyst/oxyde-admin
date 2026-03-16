from litestar import get
from litestar.exceptions import NotFoundException

from models import Post, Comment


@get("/api/posts/")
async def list_posts_handler() -> list[dict]:
    posts = await Post.objects.filter(status="published").all()
    return [
        {"id": p.id, "title": p.title, "slug": p.slug, "views": p.views} for p in posts
    ]


@get("/api/posts/{slug:str}")
async def get_post_handler(slug: str) -> dict:
    posts = await Post.objects.filter(slug=slug).all()
    if not posts:
        raise NotFoundException(detail="Post not found")
    post = posts[0]
    comments = await Comment.objects.filter(post_id=post.id, is_approved=True).all()
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "content": post.content,
        "views": post.views,
        "comments": [{"author_name": c.author_name, "body": c.body} for c in comments],
    }
