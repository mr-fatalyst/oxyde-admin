"""Admin authentication: JWT bearer tokens issued by the built-in login.

This file is identical in every framework example — the provider is
framework-agnostic, and the login endpoint is served by the admin itself.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone, timedelta

import jwt

from oxyde_admin import AdminUser, AuthProvider

from models import User

SECRET_KEY = os.environ.get("ADMIN_JWT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=2)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt_hex, digest_hex = password_hash.split("$", 1)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


class JWTAuthProvider(AuthProvider):
    async def authenticate(self, request) -> AdminUser | None:
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return None
        user_id = verify_token(header[7:])
        if user_id is None:
            return None
        users = await User.objects.filter(id=user_id).all()
        if not users or not users[0].is_admin:
            return None
        return AdminUser(id=str(users[0].id), name=users[0].name)

    async def login(self, credentials) -> str | None:
        users = await User.objects.filter(email=credentials.email).all()
        if not users:
            return None
        user = users[0]
        if not verify_password(
            credentials.password.get_secret_value(), user.password_hash
        ):
            return None
        return create_token(user.id)
