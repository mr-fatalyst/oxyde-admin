import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from litestar import Request, post, get
from litestar.exceptions import NotAuthorizedException
from pydantic import BaseModel

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


class LoginRequest(BaseModel):
    email: str
    password: str


@post("/auth/login")
async def login_handler(data: LoginRequest) -> dict:
    users = await User.objects.filter(email=data.email).all()
    if not users:
        raise NotAuthorizedException(detail="Invalid credentials")
    user = users[0]
    if not verify_password(data.password, user.password_hash):
        raise NotAuthorizedException(detail="Invalid credentials")
    return {"token": create_token(user.id)}


@get("/auth/me")
async def me_handler(request: Request) -> dict:
    user = await _get_current_user(request)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "is_admin": user.is_admin,
    }


async def check_admin(request) -> bool:
    """Verify the request comes from an admin user.

    Accepts any request object with a .headers attribute
    (works with both Starlette and Litestar Request).
    """
    try:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        user_id = verify_token(header[7:])
        if user_id is None:
            return False
        user = await User.objects.get(id=user_id)
        return user.is_admin
    except Exception:
        return False


async def _get_current_user(request: Request) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise NotAuthorizedException(detail="Missing token")
    user_id = verify_token(header[7:])
    if user_id is None:
        raise NotAuthorizedException(detail="Invalid token")
    user = await User.objects.get(id=user_id)
    return user
