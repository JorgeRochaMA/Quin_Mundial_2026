"""Small conversion helpers for values read from Google Sheets."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def clean_text(value: Any) -> str:
    """Return a stripped string while keeping empty cells predictable."""
    if value is None:
        return ""
    return str(value).strip()


def as_bool(value: Any) -> bool:
    """Convert common spreadsheet truthy values into booleans."""
    return clean_text(value).upper() in {"TRUE", "1", "YES", "SI", "SÍ"}


def as_int(value: Any, default: int = 0) -> int:
    """Convert spreadsheet values into integers without raising in the UI."""
    try:
        if clean_text(value) == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    """Convert spreadsheet values into floats without raising in the UI."""
    try:
        if clean_text(value) == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def now_iso() -> str:
    """Return a sortable timestamp for sheet writes."""
    return datetime.now().isoformat(timespec="seconds")


def serialize_cell(value: Any) -> str:
    """Serialize Python values before writing them into Google Sheets."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)
