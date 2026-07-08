from __future__ import annotations


class AdminError(Exception):
    """Base class for all oxyde-admin errors."""


class ModelNotFoundError(AdminError):
    """Raised when a model is not found in the registry."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Model '{name}' not found")


class RecordNotFoundError(AdminError):
    """Raised when a record does not exist, including unparseable PK values."""


class ConflictError(AdminError):
    """Raised when a write violates a database constraint."""


class InvalidParameterError(AdminError):
    """Raised when a query parameter or request body has an invalid shape."""


class LoginNotAvailableError(AdminError):
    """Raised when the built-in login endpoint is not enabled."""


class LoginFailedError(AdminError):
    """Raised when login credentials are rejected."""


class ExportNotAllowedError(AdminError):
    """Raised when export is disabled for a model."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Export is not allowed for '{name}'")


class ExportTooLargeError(AdminError):
    """Raised when export exceeds the maximum allowed rows."""

    def __init__(self, total: int, limit: int) -> None:
        self.total = total
        self.limit = limit
        super().__init__(f"Export too large: {total} rows exceed the limit of {limit}")
