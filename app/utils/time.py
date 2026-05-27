"""Match locking helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from utils.constants import STATUS_OPEN
from utils.data import as_int, clean_text


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


def is_match_locked(match: dict[str, Any], config: dict[str, str]) -> bool:
    """Return whether predictions should be locked for the match."""
    status = clean_text(match.get("status")).upper()
    if status != STATUS_OPEN:
        return True

    if is_global_prediction_lock_active(config):
        return True

    match_datetime = parse_match_datetime(match.get("match_date"))
    if match_datetime is None:
        return False

    lock_minutes = as_int(config.get("lock_minutes_before_match"), 60)
    return datetime.now() >= match_datetime - timedelta(minutes=lock_minutes)
