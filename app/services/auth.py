"""Authentication using a shared access code and personal passwords."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

from services.pool_repository import PoolRepository
from utils.constants import ROLE_ADMIN, ROLE_USER
from utils.data import clean_text


class AuthError(ValueError):
    """Raised when login or registration fails."""


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260_000


def _same_secret(left: str, right: str) -> bool:
    return hmac.compare_digest(clean_text(left), clean_text(right))


def _hash_password(password: str) -> str:
    """Return a salted password hash for storage."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Validate a password against a stored salted hash."""
    stored_hash = clean_text(stored_hash)
    try:
        algorithm, iterations_text, salt, expected = stored_hash.split("$", 3)
        iterations = int(iterations_text)
    except (TypeError, ValueError):
        return False

    if algorithm != PASSWORD_HASH_ALGORITHM or not salt or not expected:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Return the user data needed by the UI without secret material."""
    public = dict(user)
    public.pop("password_hash", None)
    return public


def login_or_register(
    repo: PoolRepository,
    nickname: str,
    access_code: str,
    password: str,
    full_name: str = "",
    email: str = "",
) -> dict[str, Any]:
    """Authenticate a nickname or create the user when it does not exist."""
    nickname = clean_text(nickname)
    if not nickname:
        raise AuthError("Escribe tu nickname.")

    password = str(password or "")
    if not password:
        raise AuthError("Escribe tu contraseña personal.")

    config = repo.get_config()
    user_code = config.get("pool_access_code", "")
    admin_code = config.get("admin_access_code", "")
    if not user_code and not admin_code:
        raise AuthError("Los códigos de acceso aún no están configurados.")

    is_admin = bool(admin_code) and _same_secret(access_code, admin_code)
    is_user = bool(user_code) and _same_secret(access_code, user_code)
    if not is_admin and not is_user:
        raise AuthError("Código de acceso inválido.")

    role = ROLE_ADMIN if is_admin else ROLE_USER
    existing = repo.find_user_by_nickname(nickname)
    if existing:
        stored_hash = clean_text(existing.get("password_hash"))
        if stored_hash:
            if not _verify_password(password, stored_hash):
                raise AuthError("Contraseña personal incorrecta.")
        else:
            stored_hash = _hash_password(password)
            repo.update_user_password_hash(existing["user_id"], stored_hash)
            existing["password_hash"] = stored_hash

        if is_admin and existing.get("role") != ROLE_ADMIN:
            repo.update_user_role(existing["user_id"], ROLE_ADMIN)
            existing["role"] = ROLE_ADMIN
        return _public_user(existing)

    user = repo.create_user(
        nickname=nickname,
        full_name=full_name,
        email=email,
        role=role,
        password_hash=_hash_password(password),
    )
    return _public_user(user)
