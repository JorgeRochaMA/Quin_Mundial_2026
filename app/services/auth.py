"""MVP authentication using a shared access code."""

from __future__ import annotations

import hmac
from typing import Any

from services.pool_repository import PoolRepository
from utils.constants import ROLE_ADMIN, ROLE_USER
from utils.data import clean_text


class AuthError(ValueError):
    """Raised when login or registration fails."""


def _same_secret(left: str, right: str) -> bool:
    return hmac.compare_digest(clean_text(left), clean_text(right))


def login_or_register(
    repo: PoolRepository,
    nickname: str,
    access_code: str,
    full_name: str = "",
    email: str = "",
) -> dict[str, Any]:
    """Authenticate a nickname or create the user when it does not exist."""
    nickname = clean_text(nickname)
    if not nickname:
        raise AuthError("Escribe tu nickname.")

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
        if is_admin and existing.get("role") != ROLE_ADMIN:
            repo.update_user_role(existing["user_id"], ROLE_ADMIN)
            existing["role"] = ROLE_ADMIN
        return existing

    return repo.create_user(
        nickname=nickname,
        full_name=full_name,
        email=email,
        role=role,
    )
