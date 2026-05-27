"""Ranking calculations for entries."""

from __future__ import annotations

import pandas as pd

from utils.data import as_bool, clean_text
from utils.scoring import is_exact_score


def _empty_rankings() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "position",
            "entry_id",
            "entry_name",
            "nickname",
            "paid",
            "total_points",
            "exact_scores",
            "played_matches",
            "predictions_count",
        ]
    )


def build_rankings(
    entries: pd.DataFrame,
    users: pd.DataFrame,
    predictions: pd.DataFrame,
    results: pd.DataFrame,
) -> pd.DataFrame:
    """Build standings by entry, with exact scores as the main tiebreaker."""
    if entries.empty:
        return _empty_rankings()

    active_entries = entries.copy()
    if "active" in active_entries:
        active_entries = active_entries[active_entries["active"].apply(as_bool)]

    if active_entries.empty:
        return _empty_rankings()

    scores = pd.DataFrame(columns=["entry_id", "total_points", "predictions_count"])
    if not predictions.empty:
        scored_predictions = predictions.copy()
        scored_predictions["points"] = pd.to_numeric(
            scored_predictions.get("points", 0),
            errors="coerce",
        ).fillna(0)
        scores = (
            scored_predictions.groupby("entry_id", as_index=False)
            .agg(total_points=("points", "sum"), predictions_count=("prediction_id", "count"))
        )

    exact_counts = pd.DataFrame(columns=["entry_id", "exact_scores"])
    played_counts = pd.DataFrame(columns=["entry_id", "played_matches"])
    if not predictions.empty and not results.empty:
        finished_results = results[
            results["home_score"].apply(clean_text).ne("")
            & results["away_score"].apply(clean_text).ne("")
        ]
        merged = predictions.merge(finished_results, on="match_id", how="inner")
        if not merged.empty:
            merged["is_exact"] = merged.apply(
                lambda row: is_exact_score(
                    row.get("pred_home_goals"),
                    row.get("pred_away_goals"),
                    row.get("home_score"),
                    row.get("away_score"),
                ),
                axis=1,
            )
            exact_counts = (
                merged.groupby("entry_id", as_index=False)
                .agg(exact_scores=("is_exact", "sum"))
            )
            played_counts = (
                merged.groupby("entry_id", as_index=False)
                .agg(played_matches=("match_id", "count"))
            )

    ranking = active_entries.merge(scores, on="entry_id", how="left")
    ranking = ranking.merge(exact_counts, on="entry_id", how="left")
    ranking = ranking.merge(played_counts, on="entry_id", how="left")
    if not users.empty:
        ranking = ranking.merge(users[["user_id", "nickname"]], on="user_id", how="left")
    else:
        ranking["nickname"] = ""

    ranking["total_points"] = ranking["total_points"].fillna(0).astype(int)
    ranking["exact_scores"] = ranking["exact_scores"].fillna(0).astype(int)
    ranking["played_matches"] = ranking["played_matches"].fillna(0).astype(int)
    ranking["predictions_count"] = ranking["predictions_count"].fillna(0).astype(int)
    ranking["paid"] = ranking.get("paid", "").apply(as_bool)

    ranking = ranking.sort_values(
        by=["total_points", "exact_scores", "entry_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    ranking.insert(0, "position", range(1, len(ranking) + 1))

    return ranking[
        [
            "position",
            "entry_id",
            "entry_name",
            "nickname",
            "paid",
            "total_points",
            "exact_scores",
            "played_matches",
            "predictions_count",
        ]
    ]
