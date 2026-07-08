from __future__ import annotations

import datetime as _dt
import decimal
import enum
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from oxyde_admin.auth import AdminUser, AuthRequest
from oxyde_admin.exceptions import (
    ConflictError,
    ExportNotAllowedError,
    ExportTooLargeError,
    InvalidParameterError,
    LoginFailedError,
    LoginNotAvailableError,
    ModelNotFoundError,
    RecordNotFoundError,
)
from oxyde_admin.site import AdminSite

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def json_default(obj):
    """JSON serializer for types the stdlib encoder rejects. Shared across adapters."""
    if isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, decimal.Decimal):
        # str, not float: Decimal exists to preserve exact precision
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class AbstractAdapter(AdminSite, ABC):
    """Base class for framework-specific adapters.

    Subclasses must implement the abstract methods to wire up
    the admin site to a specific web framework.
    """

    # Admin-owned exceptions only; the data layer translates ORM errors into
    # these, so the HTTP layer never imports data-source exception types.
    # Pydantic is a core dependency of the admin itself, not a data source.
    EXCEPTION_MAP: dict[type[Exception], tuple[int, Any]] = {
        ModelNotFoundError: (404, str),
        RecordNotFoundError: (404, str),
        LoginNotAvailableError: (404, str),
        LoginFailedError: (401, str),
        ExportNotAllowedError: (403, str),
        ExportTooLargeError: (400, str),
        ConflictError: (409, str),
        InvalidParameterError: (400, str),
        ValidationError: (422, lambda exc: exc.errors()),
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._app = None

    @property
    def app(self):
        if self._app is None:
            self._app = self._build_app()
        return self._app

    # ------------------------------------------------------------------
    # Abstract methods. Implement in framework adapters
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_app(self):
        """Build and return the framework-specific application."""
        ...

    @abstractmethod
    def _register_routes(self, app) -> None:
        """Register API route handlers on the application."""
        ...

    @abstractmethod
    def _register_auth_middleware(self, app) -> None:
        """Register authentication middleware on the application."""
        ...

    @abstractmethod
    def _register_exception_handlers(self, app) -> None:
        """Register exception-to-HTTP-response handlers on the application."""
        ...

    @abstractmethod
    def _register_static(self, app) -> None:
        """Register static file serving and SPA catch-all on the application."""
        ...

    # ------------------------------------------------------------------
    # Auth — the decision logic; adapters only do the plumbing
    # ------------------------------------------------------------------

    AUTH_EXEMPT_PATHS = ("/api/config", "/api/login")

    @classmethod
    def _requires_auth(cls, path: str) -> bool:
        """Decide gating for an admin-relative path (mount prefix stripped)."""
        normalized = "/" + path.strip("/")
        if not normalized.startswith("/api/"):
            return False
        return normalized not in cls.AUTH_EXEMPT_PATHS

    async def _authenticate(self, request: AuthRequest) -> AdminUser | None:
        """Run the configured provider; ``None`` means 401."""
        provider = self.auth_provider
        if provider is None:
            return AdminUser(id="anonymous")
        return await provider.authenticate(request)

    # ------------------------------------------------------------------
    # Request parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _int_param(params, name: str, default: int) -> int:
        """Parse an integer query parameter; garbage is a 400, not a 500."""
        raw = params.get(name)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise InvalidParameterError(
                f"Query parameter '{name}' must be an integer"
            ) from None

    @staticmethod
    def _bulk_ids(body: Any) -> list:
        """Extract the ``ids`` list from a bulk request body."""
        if not isinstance(body, dict) or not isinstance(body.get("ids"), list):
            raise InvalidParameterError("Request body must contain an 'ids' list")
        return body["ids"]

    @classmethod
    def _bulk_payload(cls, body: Any) -> tuple[list, dict]:
        """Extract ``ids`` and ``data`` from a bulk-update request body."""
        ids = cls._bulk_ids(body)
        if not isinstance(body.get("data"), dict):
            raise InvalidParameterError("Request body must contain a 'data' object")
        return ids, body["data"]

    # ------------------------------------------------------------------
    # SPA serving helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_static_file(path: str) -> Path | None:
        """Resolve a URL path to a static file with traversal protection."""
        if not path:
            return None
        file_path = (STATIC_DIR / path).resolve()
        if file_path.is_relative_to(STATIC_DIR) and file_path.is_file():
            return file_path
        return None

    @staticmethod
    def _render_index_html(mount_prefix: str) -> str | None:
        """Return *index.html* with ``<base href>`` injected, or *None*."""
        index_html = STATIC_DIR / "index.html"
        if not index_html.exists():
            return None
        base_href = mount_prefix.rstrip("/") + "/"
        return index_html.read_text().replace(
            "<head>",
            f'<head><base href="{base_href}">',
            1,
        )
