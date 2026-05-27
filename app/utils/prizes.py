"""Prize pool calculations."""

from __future__ import annotations

import pandas as pd

from utils.data import as_bool, as_float


def calculate_prizes(entries: pd.DataFrame, config: dict[str, str]) -> dict[str, float]:
    """Calculate active entries, total pool, and prize distribution."""
    entry_fee = as_float(config.get("entry_fee"), 200)
    first_pct = as_float(config.get("first_place_percentage"), 0.60)
    second_pct = as_float(config.get("second_place_percentage"), 0.30)
    third_pct = as_float(config.get("third_place_percentage"), 0.10)

    if entries.empty:
        entry_count = 0
    else:
        active = entries["active"].apply(as_bool) if "active" in entries else True
        entry_count = int(active.sum())

    total_pool = entry_count * entry_fee
    return {
        "paid_entries": entry_count,
        "total_entries": entry_count,
        "total_pool": total_pool,
        "first_place": total_pool * first_pct,
        "second_place": total_pool * second_pct,
        "third_place": total_pool * third_pct,
    }


def format_mxn(amount: float) -> str:
    """Format money in Mexican pesos."""
    return f"${amount:,.0f} MXN"
