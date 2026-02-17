from oxyde_admin.adapters import LitestarAdmin
from auth import check_admin
from models import User, Category, Post, Comment, Tag

admin = LitestarAdmin(
    title="Mini Blog Admin", auth_check=check_admin, login_url="/auth/login"
)

admin.register(
    User,
    list_display=["name", "email", "is_admin"],
    display_field="name",
    search_fields=["name", "email"],
    list_filter=["is_admin"],
    readonly_fields=["password_hash"],
    column_labels={"is_admin": "Admin"},
    group="Auth",
    icon="pi pi-users",
)
admin.register(
    Category,
    list_display=["name", "slug"],
    display_field="name",
    search_fields=["name"],
    group="Content",
    icon="pi pi-folder",
)
admin.register(
    Post,
    list_display=["title", "slug", "author_id", "category_id", "is_published", "views"],
    search_fields=["title", "content"],
    list_filter=["author_id", "category_id", "is_published"],
    column_labels={
        "author_id": "Author",
        "category_id": "Category",
        "is_published": "Published",
    },
    group="Content",
    icon="pi pi-file-edit",
)
admin.register(
    Tag,
    list_display=["name"],
    display_field="name",
    search_fields=["name"],
    group="Content",
    icon="pi pi-tag",
)
admin.register(
    Comment,
    list_display=["post_id", "author_name", "is_approved"],
    search_fields=["author_name", "body"],
    list_filter=["post_id", "is_approved"],
    column_labels={
        "post_id": "Post",
        "author_name": "Author",
        "is_approved": "Approved",
    },
    group="Engagement",
    icon="pi pi-comments",
)
