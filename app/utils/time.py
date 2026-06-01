"""Match locking helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from utils.constants import STATUS_BLOCKED, STATUS_CLOSED, STATUS_FINISHED, STATUS_LOCKED, STATUS_OPEN
from utils.data import clean_text


LOCKED_MATCH_STATUSES = {STATUS_LOCKED, STATUS_BLOCKED, STATUS_CLOSED, STATUS_FINISHED}


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


def has_official_result(result: dict[str, Any] | None) -> bool:
    """Return whether an official result row has usable scores."""
    if not result:
        return False

    return bool(clean_text(result.get("home_score")) and clean_text(result.get("away_score")))


def is_match_locked(
    match: dict[str, Any],
    config: dict[str, str],
    result: dict[str, Any] | None = None,
) -> bool:
    """Return whether predictions should be locked for the match."""
    status = clean_text(match.get("status")).upper() or STATUS_OPEN

    if status in LOCKED_MATCH_STATUSES:
        return True

    if has_official_result(result):
        return True

    if is_global_prediction_lock_active(config):
        return True

    return False
