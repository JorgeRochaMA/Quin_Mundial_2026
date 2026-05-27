"""Helpers for rendering user predictions."""

from __future__ import annotations

import pandas as pd

from utils.constants import AWAY_WIN, DRAW, HOME_WIN, PREDICTIONS, SHEET_COLUMNS
from utils.data import as_int, clean_text
from utils.time import parse_match_datetime


SUMMARY_COLUMNS = [
    "match_date",
    "group",
    "home_team",
    "away_team",
    "selected_result_label",
    "prediction",
    "capture_status",
    "points",
]


def build_entry_prediction_summary(
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    entry_id: str,
) -> pd.DataFrame:
    """Return every match with the selected entry prediction, if one exists."""
    if matches.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    match_rows = matches.copy()
    match_rows["_parsed_match_date"] = match_rows["match_date"].apply(parse_match_datetime)
    match_rows = match_rows.sort_values(
        ["_parsed_match_date", "group", "match_id"],
        na_position="last",
    )
    entry_predictions = pd.DataFrame(columns=SHEET_COLUMNS[PREDICTIONS])
    if not predictions.empty:
        entry_predictions = predictions[predictions["entry_id"] == entry_id].copy()

    merged = match_rows.merge(
        entry_predictions,
        on="match_id",
        how="left",
        suffixes=("", "_prediction"),
    )

    merged["prediction"] = merged.apply(_format_prediction_score, axis=1)
    merged["selected_result_label"] = merged.apply(_format_selected_result, axis=1)
    merged["capture_status"] = merged["prediction_id"].apply(
        lambda value: "Guardada" if _has_value(value) else "Pendiente"
    )
    merged["points"] = merged["points"].apply(lambda value: as_int(value, 0))

    return merged[SUMMARY_COLUMNS]


def _format_prediction_score(row: pd.Series) -> str:
    home_goals = row.get("pred_home_goals")
    away_goals = row.get("pred_away_goals")
    if not _has_value(home_goals) or not _has_value(away_goals):
        return "-"
    return f"{as_int(home_goals)} - {as_int(away_goals)}"


def _format_selected_result(row: pd.Series) -> str:
    selected_result = clean_text(row.get("selected_result"))
    if selected_result == HOME_WIN:
        return f"Gana {clean_text(row.get('home_team')) or 'local'}"
    if selected_result == AWAY_WIN:
        return f"Gana {clean_text(row.get('away_team')) or 'visitante'}"
    if selected_result == DRAW:
        return "Empate"
    return "-"


def _has_value(value: object) -> bool:
    return not pd.isna(value) and clean_text(value) != ""
