from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from oxyde.exceptions import NotFoundError, IntegrityError
from oxyde_admin.site import (
    AdminSite,
    ExportNotAllowedError,
    ExportTooLargeError,
    ModelNotFoundError,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class AbstractAdapter(AdminSite, ABC):
    """Base class for framework-specific adapters.

    Subclasses must implement the abstract methods to wire up
    the admin site to a specific web framework.
    """

    EXCEPTION_MAP: dict[type[Exception], tuple[int, Any]] = {
        ModelNotFoundError: (404, str),
        NotFoundError: (404, str),
        ExportNotAllowedError: (403, str),
        ExportTooLargeError: (400, str),
        IntegrityError: (409, str),
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
