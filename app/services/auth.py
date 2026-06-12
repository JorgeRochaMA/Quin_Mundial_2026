"""Authentication using a shared access code and personal passwords."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import get_close_matches
import hashlib
import hmac
import secrets
from typing import Any

from services.pool_repository import PoolRepository
from utils.constants import ROLE_ADMIN, ROLE_USER
from utils.data import clean_text
from utils.passwords import hash_password, verify_password


class AuthError(ValueError):
    """Raised when login or registration fails."""


SIMILAR_NICKNAME_CUTOFF = 0.82
PERSISTENT_SESSION_DAYS = 30


@dataclass(frozen=True)
class PersistentLogin:
    """Authenticated user restored from a persistent session."""

    user: dict[str, Any]
    session_id: str


def _same_secret(left: str, right: str) -> bool:
    return hmac.compare_digest(clean_text(left), clean_text(right))


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Return the user data needed by the UI without secret material."""
    public = dict(user)
    public.pop("password_hash", None)
    return public


def _hash_session_token(token: str) -> str:
    """Return a stable hash for a persistent session token."""
    return hashlib.sha256(clean_text(token).encode("utf-8")).hexdigest()


def _parse_datetime(value: object) -> datetime | None:
    """Parse a stored ISO datetime value."""
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _find_similar_nickname(nickname: str, existing_nicknames: list[str]) -> str | None:
    """Return an existing nickname that is close enough to block accidental duplicates."""
    normalized = clean_text(nickname).lower()
    if not normalized:
        return None

    normalized_to_original = {
        clean_text(existing).lower(): clean_text(existing)
        for existing in existing_nicknames
        if clean_text(existing)
    }
    candidates = [candidate for candidate in normalized_to_original if candidate != normalized]

    contains_matches = [
        candidate
        for candidate in candidates
        if len(normalized) >= 4
        and len(candidate) >= 4
        and (normalized in candidate or candidate in normalized)
    ]
    if contains_matches:
        best = min(
            contains_matches,
            key=lambda candidate: (abs(len(candidate) - len(normalized)), candidate),
        )
        return normalized_to_original[best]

    close_matches = get_close_matches(
        normalized,
        candidates,
        n=1,
        cutoff=SIMILAR_NICKNAME_CUTOFF,
    )
    if close_matches:
        return normalized_to_original[close_matches[0]]

    return None


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
            if not verify_password(password, stored_hash):
                raise AuthError("Contraseña personal incorrecta.")
        else:
            stored_hash = hash_password(password)
            repo.update_user_password_hash(existing["user_id"], stored_hash)
            existing["password_hash"] = stored_hash

        if is_admin and existing.get("role") != ROLE_ADMIN:
            repo.update_user_role(existing["user_id"], ROLE_ADMIN)
            existing["role"] = ROLE_ADMIN
        return _public_user(existing)

    similar_nickname = _find_similar_nickname(nickname, repo.list_active_user_nicknames())
    if similar_nickname:
        raise AuthError(
            (
                f"No encontramos '{nickname}', pero existe un usuario parecido: "
                f"'{similar_nickname}'. Revisa tu nickname antes de crear uno nuevo."
            )
        )

    user = repo.create_user(
        nickname=nickname,
        full_name=full_name,
        email=email,
        role=role,
        password_hash=hash_password(password),
    )
    return _public_user(user)


def create_persistent_login_session(
    repo: PoolRepository,
    user_id: str,
    device_label: str = "Dispositivo recordado",
) -> tuple[str, dict[str, Any]]:
    """Create a persistent login session and return the raw token once."""
    token = secrets.token_urlsafe(48)
    expires_at = (datetime.now() + timedelta(days=PERSISTENT_SESSION_DAYS)).isoformat(timespec="seconds")
    session = repo.create_persistent_session(
        user_id=user_id,
        token_hash=_hash_session_token(token),
        expires_at=expires_at,
        device_label=device_label,
    )
    return token, session


def restore_persistent_login(repo: PoolRepository, token: str) -> PersistentLogin | None:
    """Restore a user from a persistent session token if it is valid."""
    token = clean_text(token)
    if not token:
        return None

    session = repo.find_active_session_by_token_hash(_hash_session_token(token))
    if not session:
        return None

    session_id = clean_text(session.get("session_id"))
    expires_at = _parse_datetime(session.get("expires_at"))

    if not session_id or expires_at is None or expires_at <= datetime.now():
        if session_id:
            repo.revoke_session(session_id)
        return None

    user = repo.find_user_by_id(clean_text(session.get("user_id")))
    if not user:
        repo.revoke_session(session_id)
        return None

    if clean_text(user.get("role")).upper() != ROLE_USER:
        repo.revoke_session(session_id)
        return None

    return PersistentLogin(user=_public_user(user), session_id=session_id)
