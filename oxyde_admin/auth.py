from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Mapping

from pydantic import BaseModel, SecretStr


@dataclass
class AuthRequest:
    """Framework-agnostic view of an incoming request.

    ``native`` holds the original framework request object as an escape
    hatch; portable providers should not rely on it.
    """

    headers: Mapping[str, str]  # keys are lowercase
    cookies: Mapping[str, str]
    path: str  # admin-relative, mount prefix stripped
    method: str
    native: Any = None


@dataclass
class AdminUser:
    """Authenticated admin identity."""

    id: str
    name: str = ""
    is_authenticated: bool = True
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)  # "users:delete" style


class DefaultCredentials(BaseModel):
    """Login form shape used when a provider does not declare its own."""

    email: str
    password: SecretStr


class AuthProvider(ABC):
    """Authentication backend for the admin.

    ``credentials_model`` describes the login form: the frontend renders it
    from the model's JSON schema (``SecretStr`` fields become password
    inputs). Implement ``login`` to enable the built-in ``/api/login``
    endpoint; leave it unimplemented to authenticate against an external
    ``login_url`` instead.
    """

    credentials_model: ClassVar[type[BaseModel]] = DefaultCredentials

    @abstractmethod
    async def authenticate(self, request: AuthRequest) -> AdminUser | None:
        """Return the authenticated user, or ``None`` for a 401."""

    async def login(self, credentials: BaseModel) -> str | None:
        """Exchange validated credentials for a token; ``None`` on failure."""
        raise NotImplementedError


def has_builtin_login(provider: AuthProvider) -> bool:
    """True if the provider overrides ``login()``."""
    return type(provider).login is not AuthProvider.login


# TODO(0.7.0): remove — auth_check deprecation tail
class _CallbackProvider(AuthProvider):
    """Wraps a legacy ``auth_check`` callable.

    The callback keeps its original contract: it receives the native
    framework request and returns a truthy value to allow the request.
    """

    def __init__(self, check: Callable) -> None:
        self._check = check

    async def authenticate(self, request: AuthRequest) -> AdminUser | None:
        if inspect.iscoroutinefunction(self._check):
            allowed = await self._check(request.native)
        else:
            allowed = self._check(request.native)
        return AdminUser(id="legacy") if allowed else None
