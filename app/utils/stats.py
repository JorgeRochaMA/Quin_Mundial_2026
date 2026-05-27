"""Statistics for the prediction pool."""

from __future__ import annotations

import pandas as pd

from utils.rankings import build_rankings
from utils.scoring import is_exact_score


def build_pool_stats(
    entries: pd.DataFrame,
    users: pd.DataFrame,
    predictions: pd.DataFrame,
    results: pd.DataFrame,
    matches: pd.DataFrame,
) -> dict[str, object]:
    """Return friendly statistics for the stats page."""
    rankings = build_rankings(entries, users, predictions, results)
    if rankings.empty:
        return {
            "most_exact": None,
            "best_accuracy": None,
            "riskiest": None,
            "popular_score": None,
            "group_summary": pd.DataFrame(),
        }

    completed = predictions.merge(results, on="match_id", how="inner")
    if not completed.empty:
        completed["points"] = pd.to_numeric(completed["points"], errors="coerce").fillna(0)
        completed["is_exact"] = completed.apply(
            lambda row: is_exact_score(
                row.get("pred_home_goals"),
                row.get("pred_away_goals"),
                row.get("home_score"),
                row.get("away_score"),
            ),
            axis=1,
        )
        completed["predicted_goals"] = (
            pd.to_numeric(completed["pred_home_goals"], errors="coerce").fillna(0)
            + pd.to_numeric(completed["pred_away_goals"], errors="coerce").fillna(0)
        )
    else:
        completed = pd.DataFrame()

    most_exact = rankings.sort_values(
        ["exact_scores", "total_points"],
        ascending=[False, False],
    ).head(1)

    best_accuracy = None
    riskiest = None
    popular_score = None
    if not predictions.empty:
        score_counts = predictions.copy()
        score_counts["pred_home_goals"] = pd.to_numeric(
            score_counts["pred_home_goals"],
            errors="coerce",
        )
        score_counts["pred_away_goals"] = pd.to_numeric(
            score_counts["pred_away_goals"],
            errors="coerce",
        )
        score_counts = score_counts.dropna(subset=["pred_home_goals", "pred_away_goals"])
        if not score_counts.empty:
            score_counts["scoreline"] = (
                score_counts["pred_home_goals"].astype(int).astype(str)
                + " - "
                + score_counts["pred_away_goals"].astype(int).astype(str)
            )
            popular_score = (
                score_counts.groupby("scoreline", as_index=False)
                .agg(predictions=("prediction_id", "count"))
                .sort_values(["predictions", "scoreline"], ascending=[False, True])
                .head(1)
            )

    if not completed.empty:
        entry_stats = (
            completed.groupby("entry_id", as_index=False)
            .agg(
                total_points=("points", "sum"),
                matches_scored=("match_id", "count"),
                avg_predicted_goals=("predicted_goals", "mean"),
            )
        )
        entry_stats["accuracy"] = entry_stats["total_points"] / (entry_stats["matches_scored"] * 5)
        entry_stats = entry_stats.merge(
            rankings[["entry_id", "entry_name", "nickname"]],
            on="entry_id",
            how="left",
        )
        best_accuracy = entry_stats.sort_values("accuracy", ascending=False).head(1)
        riskiest = entry_stats.sort_values("avg_predicted_goals", ascending=False).head(1)

    group_summary = pd.DataFrame()
    if not completed.empty and not matches.empty:
        completed_with_matches = completed.merge(
            matches[["match_id", "group"]],
            on="match_id",
            how="left",
        )
        group_summary = (
            completed_with_matches.groupby("group", as_index=False)
            .agg(
                avg_points=("points", "mean"),
                predictions=("prediction_id", "count"),
                exact_scores=("is_exact", "sum"),
            )
            .sort_values("avg_points", ascending=False)
        )

    return {
        "most_exact": None if most_exact.empty else most_exact.iloc[0].to_dict(),
        "best_accuracy": None if best_accuracy is None or best_accuracy.empty else best_accuracy.iloc[0].to_dict(),
        "riskiest": None if riskiest is None or riskiest.empty else riskiest.iloc[0].to_dict(),
        "popular_score": None if popular_score is None or popular_score.empty else popular_score.iloc[0].to_dict(),
        "group_summary": group_summary,
    }
