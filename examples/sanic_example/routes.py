from sanic import Blueprint, json
from sanic.exceptions import NotFound

from models import Post, Comment

bp = Blueprint("blog", url_prefix="/api")


@bp.get("/posts/")
async def list_posts(request):
    posts = await Post.objects.filter(status="published").all()
    return json(
        [
            {"id": p.id, "title": p.title, "slug": p.slug, "views": p.views}
            for p in posts
        ]
    )


@bp.get("/posts/<slug:str>")
async def get_post(request, slug: str):
    posts = await Post.objects.filter(slug=slug).all()
    if not posts:
        raise NotFound("Post not found")
    post = posts[0]
    comments = await Comment.objects.filter(post_id=post.id, is_approved=True).all()
    return json(
        {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "content": post.content,
            "views": post.views,
            "comments": [
                {"author_name": c.author_name, "body": c.body} for c in comments
            ],
        }
    )
