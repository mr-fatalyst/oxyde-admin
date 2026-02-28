import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from quart import Blueprint, request, jsonify

from models import User

SECRET_KEY = "change-me-in-production-32bytes!"
ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=24)

bp = Blueprint("auth", __name__, url_prefix="/auth")


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


@bp.post("/login")
async def login():
    body = await request.get_json()
    users = await User.objects.filter(email=body["email"]).all()
    if not users:
        return jsonify({"detail": "Invalid credentials"}), 401
    user = users[0]
    if not verify_password(body["password"], user.password_hash):
        return jsonify({"detail": "Invalid credentials"}), 401
    return jsonify({"token": create_token(user.id)})


@bp.get("/me")
async def me():
    user = await _get_current_user()
    return jsonify(
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "is_admin": user.is_admin,
        }
    )


async def check_admin(req) -> bool:
    """Verify the request comes from an admin user.

    Accepts any request object with a .headers attribute
    (works with Quart Request).
    """
    try:
        header = req.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        user_id = verify_token(header[7:])
        if user_id is None:
            return False
        user = await User.objects.get(id=user_id)
        return user.is_admin
    except Exception:
        return False


async def _get_current_user() -> User:
    from quart import abort

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        abort(401, "Missing token")
    user_id = verify_token(header[7:])
    if user_id is None:
        abort(401, "Invalid token")
    user = await User.objects.get(id=user_id)
    return user
