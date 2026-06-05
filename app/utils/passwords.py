"""Password hashing helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from utils.data import clean_text


PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """Return a salted password hash for storage."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
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
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)
