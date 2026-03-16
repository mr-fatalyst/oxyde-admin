import falcon

from models import Post, Comment


class PostsResource:
    async def on_get(self, req, resp):
        posts = await Post.objects.filter(status="published").all()
        resp.media = [
            {"id": p.id, "title": p.title, "slug": p.slug, "views": p.views}
            for p in posts
        ]


class PostResource:
    async def on_get(self, req, resp, slug):
        posts = await Post.objects.filter(slug=slug).all()
        if not posts:
            raise falcon.HTTPNotFound(description="Post not found")
        post = posts[0]
        comments = await Comment.objects.filter(post_id=post.id, is_approved=True).all()
        resp.media = {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "content": post.content,
            "views": post.views,
            "comments": [
                {"author_name": c.author_name, "body": c.body} for c in comments
            ],
        }
