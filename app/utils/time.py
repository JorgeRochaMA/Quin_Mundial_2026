"""Match locking helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from utils.constants import STATUS_BLOCKED, STATUS_CLOSED, STATUS_FINISHED, STATUS_LOCKED, STATUS_OPEN
from utils.data import clean_text


LOCKED_MATCH_STATUSES = {STATUS_LOCKED, STATUS_BLOCKED, STATUS_CLOSED, STATUS_FINISHED}


@dataclass(frozen=True)
class MatchLockState:
    """Detailed lock state for one match."""

    raw_status: str
    normalized_status: str
    has_official_result: bool
    global_locked: bool
    locked: bool
    reason: str


def parse_match_datetime(value: Any) -> datetime | None:
    """Parse a spreadsheet match datetime value."""
    text = clean_text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def is_global_prediction_lock_active(config: dict[str, str]) -> bool:
    """Return whether the pool-wide prediction edit cutoff has passed."""
    lock_at = parse_match_datetime(config.get("predictions_lock_at"))
    if lock_at is None:
        return False
    return datetime.now() >= lock_at


def normalize_match_status(value: Any) -> str:
    """Normalize spreadsheet match status values."""
    return clean_text(value).upper() or STATUS_OPEN


def has_official_result(result: dict[str, Any] | None) -> bool:
    """Return whether an official result row has usable scores."""
    if not result:
        return False

    return bool(clean_text(result.get("home_score")) and clean_text(result.get("away_score")))


def get_match_lock_state(
    match: dict[str, Any],
    config: dict[str, str],
    result: dict[str, Any] | None = None,
) -> MatchLockState:
    """Return detailed prediction lock state for the match."""
    raw_status = clean_text(match.get("status"))
    status = normalize_match_status(raw_status)
    official_result = has_official_result(result)
    global_locked = is_global_prediction_lock_active(config)

    if status in LOCKED_MATCH_STATUSES:
        return MatchLockState(raw_status, status, official_result, global_locked, True, f"status={status}")

    if official_result:
        return MatchLockState(raw_status, status, True, global_locked, True, "resultado oficial")

    if global_locked:
        return MatchLockState(raw_status, status, False, True, True, "cierre global")

    return MatchLockState(raw_status, status, False, False, False, "abierto")


def is_match_locked(
    match: dict[str, Any],
    config: dict[str, str],
    result: dict[str, Any] | None = None,
) -> bool:
    """Return whether predictions should be locked for the match."""
    return get_match_lock_state(match, config, result).locked
