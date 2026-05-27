"""Tests for pool statistics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from utils.constants import ENTRIES, MATCHES, PREDICTIONS, RESULTS, SHEET_COLUMNS, USERS
from utils.stats import build_pool_stats


class PoolStatsTest(unittest.TestCase):
    def test_stats_include_popular_score_and_group_summary(self) -> None:
        entries = pd.DataFrame(
            [
                {
                    "entry_id": "e1",
                    "user_id": "u1",
                    "entry_name": "George #1",
                    "paid": "TRUE",
                    "amount_paid": "200",
                    "created_at": "",
                    "active": "TRUE",
                }
            ],
            columns=SHEET_COLUMNS[ENTRIES],
        )
        users = pd.DataFrame(
            [
                {
                    "user_id": "u1",
                    "full_name": "George",
                    "nickname": "George",
                    "email": "",
                    "role": "USER",
                    "active": "TRUE",
                }
            ],
            columns=SHEET_COLUMNS[USERS],
        )
        matches = pd.DataFrame(
            [
                {
                    "match_id": "m1",
                    "stage": "Group Stage",
                    "group": "A",
                    "match_date": "2026-06-11 13:00",
                    "home_team": "Mexico",
                    "away_team": "South Africa",
                    "stadium": "",
                    "city": "",
                    "status": "FINISHED",
                }
            ],
            columns=SHEET_COLUMNS[MATCHES],
        )
        results = pd.DataFrame(
            [{"match_id": "m1", "home_score": "2", "away_score": "1", "updated_at": ""}],
            columns=SHEET_COLUMNS[RESULTS],
        )
        predictions = pd.DataFrame(
            [
                {
                    "prediction_id": "p1",
                    "entry_id": "e1",
                    "match_id": "m1",
                    "selected_result": "HOME_WIN",
                    "pred_home_goals": "2",
                    "pred_away_goals": "1",
                    "points": "5",
                    "submitted_at": "",
                }
            ],
            columns=SHEET_COLUMNS[PREDICTIONS],
        )

        stats = build_pool_stats(entries, users, predictions, results, matches)

        self.assertEqual(stats["popular_score"]["scoreline"], "2 - 1")
        self.assertEqual(stats["group_summary"].iloc[0]["group"], "A")
        self.assertEqual(stats["group_summary"].iloc[0]["exact_scores"], 1)


if __name__ == "__main__":
    unittest.main()
