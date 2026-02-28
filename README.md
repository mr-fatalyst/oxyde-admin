<p align="center">
  <img src="https://raw.githubusercontent.com/mr-fatalyst/oxyde-admin/main/logo.png" alt="Logo" width="300">
</p>

<p align="center"> <b>Oxyde Admin</b> Auto-generated admin panel for <a href="https://github.com/mr-fatalyst/oxyde">Oxyde ORM</a> with zero boilerplate. </p>

<p align="center">
  <img src="https://img.shields.io/github/license/mr-fatalyst/oxyde-admin">
  <img src="https://github.com/mr-fatalyst/oxyde-admin/actions/workflows/test.yml/badge.svg">
  <img src="https://img.shields.io/pypi/v/oxyde-admin">
  <img src="https://img.shields.io/pypi/pyversions/oxyde-admin">
  <img src="https://static.pepy.tech/badge/oxyde-admin" alt="PyPI Downloads">
</p>

---

## Features

- **Automatic CRUD** - list, create, edit, delete from your Oxyde models
- **Search & filters** - text search across fields, column filters (FK, bool, string)
- **Foreign key handling** - select dropdowns with inline create dialog
- **Export** - CSV and JSON export with applied filters
- **Authentication** - pluggable auth via callback, JWT-ready
- **Theming** - 3 presets, 17 colors, 8 surface palettes
- **Bulk operations** - bulk delete and update from list view
- **Multi-framework** - FastAPI, Litestar, Sanic, Quart and Falcon adapters

![oxyde-admin list view](https://raw.githubusercontent.com/mr-fatalyst/oxyde-admin/main/images/screenshot-list.png)

## Installation

```bash
pip install oxyde-admin
```

## Quick start

```python
from fastapi import FastAPI
from oxyde import db
from oxyde_admin import FastAPIAdmin

from models import User, Post, Comment

admin = FastAPIAdmin(title="My Admin")
admin.register(User, list_display=["name", "email"], search_fields=["name", "email"])
admin.register(Post, list_display=["title", "is_published"], list_filter=["is_published"])
admin.register(Comment)

app = FastAPI(lifespan=db.lifespan(default="sqlite:///app.db"))
app.mount("/admin", admin.app)
```

Open `http://localhost:8000/admin/` and get a full CRUD interface for your models.

![edit form](https://raw.githubusercontent.com/mr-fatalyst/oxyde-admin/main/images/screenshot-detail.png)

## Frameworks

### FastAPI

```python
from oxyde_admin import FastAPIAdmin

admin = FastAPIAdmin(title="My Admin")
# register models...
app.mount("/admin", admin.app)
```

### Litestar

```python
from litestar import Litestar, asgi
from oxyde_admin import LitestarAdmin

admin = LitestarAdmin(title="My Admin")
# register models...

app = Litestar(
    route_handlers=[
        asgi(path="/admin", is_mount=True)(admin.app),
    ],
)
```

### Sanic

```python
from sanic import Sanic
from oxyde_admin import SanicAdmin

admin = SanicAdmin(title="My Admin")
# register models...

app = Sanic("MyApp")
admin.register_exception_handlers(app)
app.blueprint(admin.blueprint)
```

### Quart

```python
from quart import Quart
from oxyde_admin import QuartAdmin

admin = QuartAdmin(title="My Admin")
# register models...

app = Quart(__name__)
admin.init_app(app)
```

### Falcon

```python
import falcon.asgi
from oxyde_admin import FalconAdmin

admin = FalconAdmin(title="My Admin")
# register models...

app = falcon.asgi.App()
admin.init_app(app)
```

## Model registration

```python
admin.register(
    Post,
    list_display=["title", "author_id", "is_published", "views"],
    search_fields=["title", "content"],
    list_filter=["author_id", "is_published"],
    readonly_fields=["views"],
    ordering=["-views"],
    display_field="title",
    column_labels={"author_id": "Author", "is_published": "Published"},
    exportable=True,
    group="Content",
    icon="pi pi-file-edit",
)
```

| Parameter | Description |
|---|---|
| `list_display` | Columns shown in the list view |
| `search_fields` | Fields included in text search |
| `list_filter` | Columns available as filters |
| `readonly_fields` | Fields disabled in the edit form |
| `ordering` | Default sort order (prefix `-` for descending) |
| `display_field` | Field used as label in FK dropdowns |
| `column_labels` | Custom column headers |
| `exportable` | Enable CSV/JSON export (default: `True`) |
| `group` | Sidebar group name |
| `icon` | Sidebar icon ([PrimeIcons](https://primevue.org/icons/)) |

You can also auto-register all models at once:

```python
admin.register_all()

# or exclude specific models
admin.register_all(exclude={InternalModel})
```

## Theming

```python
from oxyde_admin import Preset, PrimaryColor, Surface

admin = FastAPIAdmin(
    title="My Admin",
    preset=Preset.AURA,
    primary_color=PrimaryColor.TEAL,
    surface=Surface.ZINC,
)
```

![themes](https://raw.githubusercontent.com/mr-fatalyst/oxyde-admin/main/images/screenshot-themes.png)

**Presets:** `AURA`, `LARA`, `NORA`

**Colors:** `NOIR` `EMERALD` `GREEN` `LIME` `ORANGE` `AMBER` `YELLOW` `TEAL` `CYAN` `SKY` `BLUE` `INDIGO` `VIOLET` `PURPLE` `FUCHSIA` `PINK` `ROSE`

**Surfaces:** `SLATE` `GRAY` `ZINC` `NEUTRAL` `STONE` `SOHO` `VIVA` `OCEAN`

## Authentication

Pass an `auth_check` callback and a `login_url`:

```python
async def check_admin(request) -> bool:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    return await verify_admin_token(token)

admin = FastAPIAdmin(
    auth_check=check_admin,
    login_url="/auth/login",
)
```

The admin UI redirects unauthenticated users to `login_url`. Your login endpoint should return a JSON response with a token - the frontend stores it and sends as `Authorization: Bearer <token>` on every request.

## License

This project is licensed under the terms of the MIT license.
