"""Scoring rules for predictions."""

from __future__ import annotations

from typing import Any

from utils.constants import AWAY_WIN, DRAW, HOME_WIN
from utils.data import as_int, clean_text


def result_from_score(home_goals: Any, away_goals: Any) -> str:
    """Return HOME_WIN, AWAY_WIN, or DRAW from a score line."""
    home = as_int(home_goals)
    away = as_int(away_goals)
    if home > away:
        return HOME_WIN
    if away > home:
        return AWAY_WIN
    return DRAW


def is_exact_score(
    pred_home_goals: Any,
    pred_away_goals: Any,
    actual_home_goals: Any,
    actual_away_goals: Any,
) -> bool:
    """Return whether the predicted score equals the official score."""
    if clean_text(actual_home_goals) == "" or clean_text(actual_away_goals) == "":
        return False
    return (
        as_int(pred_home_goals) == as_int(actual_home_goals)
        and as_int(pred_away_goals) == as_int(actual_away_goals)
    )


def calculate_prediction_points(
    selected_result: Any,
    pred_home_goals: Any,
    pred_away_goals: Any,
    actual_home_goals: Any,
    actual_away_goals: Any,
    points_result: int = 3,
    points_exact: int = 2,
) -> int:
    """Calculate points for one prediction and official result."""
    if clean_text(actual_home_goals) == "" or clean_text(actual_away_goals) == "":
        return 0

    points = 0
    actual_result = result_from_score(actual_home_goals, actual_away_goals)
    if clean_text(selected_result) == actual_result:
        points += points_result
    if is_exact_score(
        pred_home_goals,
        pred_away_goals,
        actual_home_goals,
        actual_away_goals,
    ):
        points += points_exact
    return points
