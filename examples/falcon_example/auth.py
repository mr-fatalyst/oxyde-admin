import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import jwt
import falcon

from models import User

SECRET_KEY = "change-me-in-production-32bytes!"
ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=24)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, digest = password_hash.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == digest


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


class LoginResource:
    async def on_post(self, req, resp):
        body = await req.get_media()
        users = await User.objects.filter(email=body["email"]).all()
        if not users:
            resp.status = 401
            resp.media = {"detail": "Invalid credentials"}
            return
        user = users[0]
        if not verify_password(body["password"], user.password_hash):
            resp.status = 401
            resp.media = {"detail": "Invalid credentials"}
            return
        resp.media = {"token": create_token(user.id)}


class MeResource:
    async def on_get(self, req, resp):
        user = await _get_current_user(req)
        resp.media = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "is_admin": user.is_admin,
        }


async def check_admin(req) -> bool:
    """Verify the request comes from an admin user.

    Accepts any request object with a .headers attribute
    (works with Falcon Request).
    """
    try:
        header = req.get_header("Authorization") or ""
        if not header.startswith("Bearer "):
            return False
        user_id = verify_token(header[7:])
        if user_id is None:
            return False
        user = await User.objects.get(id=user_id)
        return user.is_admin
    except Exception:
        return False


async def _get_current_user(req) -> User:
    header = req.get_header("Authorization") or ""
    if not header.startswith("Bearer "):
        raise falcon.HTTPUnauthorized(description="Missing token")
    user_id = verify_token(header[7:])
    if user_id is None:
        raise falcon.HTTPUnauthorized(description="Invalid token")
    user = await User.objects.get(id=user_id)
    return user
