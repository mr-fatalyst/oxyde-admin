from quart import Blueprint, jsonify, abort

from models import Post, Comment

bp = Blueprint("blog", __name__, url_prefix="/api")


@bp.get("/posts/")
async def list_posts():
    posts = await Post.objects.filter(is_published=True).all()
    return jsonify(
        [
            {"id": p.id, "title": p.title, "slug": p.slug, "views": p.views}
            for p in posts
        ]
    )


@bp.get("/posts/<slug>")
async def get_post(slug: str):
    posts = await Post.objects.filter(slug=slug).all()
    if not posts:
        abort(404, "Post not found")
    post = posts[0]
    comments = await Comment.objects.filter(post_id=post.id, is_approved=True).all()
    return jsonify(
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
