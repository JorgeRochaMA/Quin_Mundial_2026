"""Input validation helpers for business operations."""

from __future__ import annotations

import re
from typing import Any

from utils.constants import MATCH_STATUSES, RESULT_VALUES
from utils.data import as_int, clean_text


SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_resource_id(value: Any, field_name: str = "identifier") -> str:
    """Validate IDs before using them to select or update sheet rows."""
    text = clean_text(value)
    if not SAFE_ID_PATTERN.match(text):
        raise ValueError(f"Identificador inválido: {field_name}.")
    return text


def validate_display_text(value: Any, field_name: str, max_length: int = 80) -> str:
    """Validate short user-facing text stored in Sheets."""
    text = clean_text(value)
    if not text:
        raise ValueError(f"El campo {field_name} es obligatorio.")
    if len(text) > max_length:
        raise ValueError(f"El campo {field_name} es demasiado largo.")
    return text


def validate_score(value: Any, field_name: str) -> int:
    """Validate a football score value."""
    score = as_int(value, -1)
    if score < 0 or score > 20:
        raise ValueError(f"Marcador inválido: {field_name}.")
    return score


def validate_match_status(value: Any) -> str:
    """Validate a match status."""
    status = clean_text(value).upper()
    if status not in MATCH_STATUSES:
        raise ValueError("Estado de partido inválido.")
    return status


def validate_selected_result(value: Any) -> str:
    """Validate a prediction result value."""
    result = clean_text(value).upper()
    if result not in RESULT_VALUES:
        raise ValueError("Resultado seleccionado inválido.")
    return result
