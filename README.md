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
- **Many-to-many relations** - multi-select widget with junction-table sync
- **Enum & array fields** - `Enum` columns rendered as dropdowns, `list[T]` as array editors
- **Streaming export** - CSV / JSON export of large tables in chunks, with row caps
- **Bulk operations** - bulk delete and update from the list view
- **Authentication** - pluggable sync/async callback, JWT-ready
- **Theming** - 3 presets, 17 colors, 8 surface palettes
- **Multi-framework** - FastAPI, Litestar, Sanic, Quart and Falcon adapters

![oxyde-admin list view](https://raw.githubusercontent.com/mr-fatalyst/oxyde-admin/main/images/screenshot-list.png)

## Requirements

- Python ≥ 3.10
- [`oxyde`](https://github.com/mr-fatalyst/oxyde) ≥ 0.7.0
- One of the supported frameworks (`fastapi` / `litestar` / `sanic` / `quart` / `falcon`)
- An ASGI server (e.g. `uvicorn`, `hypercorn`)

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
The admin ships its own SPA frontend, so no separate frontend build is required —
the static assets are served by the same mount.

![edit form](https://raw.githubusercontent.com/mr-fatalyst/oxyde-admin/main/images/screenshot-detail.png)

## Configuration

All adapters accept the same constructor parameters:

| Parameter | Default | Description |
|---|---|---|
| `title` | `"Oxyde Admin"` | Title shown in the UI |
| `prefix` | `"/admin"` | URL prefix (FastAPI / Sanic / Quart / Falcon; on Litestar set the path via mount) |
| `preset` | `Preset.AURA` | PrimeVue preset |
| `primary_color` | `PrimaryColor.SKY` | Accent color |
| `surface` | `Surface.SLATE` | Surface palette |
| `per_page` | `100` | Maximum page size for the list view |
| `export_chunk_size` | `10_000` | Rows per chunk while streaming an export |
| `max_export_rows` | `100_000` | Hard cap on total exported rows |
| `auth_provider` | `None` | `AuthProvider` instance (see [Authentication](#authentication)) |
| `auth_check` | `None` | **Deprecated, removed in 0.7.0** — legacy callable `(request) -> bool` |
| `login_url` | `None` | External login endpoint used when the provider has no `login()` |

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

admin = SanicAdmin(title="My Admin", prefix="/admin")
# register models...

app = Sanic("MyApp")
admin.register_exception_handlers(app)
app.blueprint(admin.blueprint)
```

### Quart

```python
from quart import Quart
from oxyde_admin import QuartAdmin

admin = QuartAdmin(title="My Admin", prefix="/admin")
# register models...

app = Quart(__name__)
admin.init_app(app)
```

### Falcon

```python
import falcon.asgi
from oxyde_admin import FalconAdmin

admin = FalconAdmin(title="My Admin", prefix="/admin")
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
| `exclude_fields` | Fields stripped from API responses, schema and export, and blocked on write (e.g. `password_hash`) |
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

## Field types

The admin reads field metadata from `_db_meta` and renders an appropriate widget:

| Type | Widget |
|---|---|
| `str` / `int` / `float` | Text / number input |
| `bool` | Toggle |
| `date` / `datetime` | Date / datetime picker |
| `UUID` | Text input |
| `Enum` | Dropdown with the enum members |
| `list[T]` | Array editor (chips for primitive item types) |
| Foreign key | Searchable dropdown with inline create dialog |
| Many-to-many | Multi-select; junction rows synced on save |

> **Tip:** Foreign-key and M2M target models must also be registered. Use
> `display_field` on the *target* model to control the label shown in
> dropdowns; otherwise the first string field (or the primary key) is used.

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

Implement an `AuthProvider` and pass it to the adapter:

```python
from oxyde_admin import AdminUser, AuthProvider, FastAPIAdmin

class MyAuthProvider(AuthProvider):
    async def authenticate(self, request) -> AdminUser | None:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        user = await load_admin_by_token(token)      # your logic
        return AdminUser(id=str(user.id), name=user.name) if user else None

    async def login(self, credentials) -> str | None:
        user = await check_password(
            credentials.email, credentials.password.get_secret_value()
        )
        return issue_token(user) if user else None   # your logic

admin = FastAPIAdmin(auth_provider=MyAuthProvider())
```

- `authenticate` receives a framework-agnostic `AuthRequest` — `headers`
  (lowercase keys), `cookies`, `path`, `method`, plus the `native` framework
  request as an escape hatch. The same provider works on every supported
  framework. Return `AdminUser` to allow the request, `None` for a 401.
- Implementing `login` enables the built-in `POST /api/login` endpoint and
  the admin's own login form. The form is rendered from
  `AuthProvider.credentials_model`, a Pydantic model (default: `email` +
  `password`). Declare your own model to change the fields — `SecretStr`
  fields render as password inputs:

  ```python
  class MyCredentials(BaseModel):
      username: str
      password: SecretStr
      otp: str | None = Field(default=None, title="One-time code")

  class MyAuthProvider(AuthProvider):
      credentials_model = MyCredentials
  ```

- Without `login()`, set `login_url` instead: the admin's login form posts
  `POST {"email": ..., "password": ...}` there and expects
  `{"token": "<...>"}` back.
- `GET /api/config` and `POST /api/login` are intentionally **not gated** so
  the login screen can bootstrap itself.
- The frontend stores the token in `localStorage` under `admin_token` and
  sends `Authorization: Bearer <token>` on every request; on a `401` it
  clears the token and shows the login screen. Bearer auth is immune to CSRF;
  the localStorage-vs-cookie trade-off is deliberate.
- Rate limiting / brute-force protection of the login endpoint is the host
  application's responsibility.

### Migrating from `auth_check`

The `auth_check` callable (native request in, `bool` out) is deprecated and
will be removed in 0.7.0; it keeps working with a `DeprecationWarning` until
then. To migrate, move its body into `AuthProvider.authenticate`: the native
request is available as `request.native`, and you return `AdminUser(...)`
instead of `True`.

## API

The admin UI talks to the backend through the following endpoints (relative to
the admin `prefix`):

```
GET    /api/config
POST   /api/login                 { "email": ..., "password": ... } → { "token": ... }
GET    /api/models
GET    /api/models/counts
GET    /api/<model>/schema
GET    /api/<model>?page=&per_page=&ordering=&search=&<filter>=
POST   /api/<model>
GET    /api/<model>/<pk>
PATCH  /api/<model>/<pk>
DELETE /api/<model>/<pk>
GET    /api/<model>/options?search=&limit=&include=
GET    /api/<model>/export?format=csv|json&ids=&ordering=&search=
POST   /api/<model>/bulk-delete   { "ids": [...] }
POST   /api/<model>/bulk-update   { "ids": [...], "data": {...} }
```

`<model>` is the table name (e.g. `users`, not `User`). Schema responses
include `x-db-*` extensions (primary key, FK target, nullable, default,
db type, max length, enum members, array item type, M2M target / through)
that you can use to drive a custom UI — see
[`oxyde_admin/schema.py`](oxyde_admin/schema.py) for the full list.

## Examples

Working applications with auth, fixtures, FK / M2M relations, and enum / array
fields are in [`examples/`](examples/) for each supported framework
(FastAPI, Litestar, Sanic, Quart, Falcon).

## License

This project is licensed under the terms of the MIT license.
