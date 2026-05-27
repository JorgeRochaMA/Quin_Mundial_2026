"""Tests for rankings."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from utils.rankings import build_rankings


class RankingsTest(unittest.TestCase):
    def test_rankings_are_entry_based(self) -> None:
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
            ]
        )
        entries = pd.DataFrame(
            [
                {
                    "entry_id": "e1",
                    "user_id": "u1",
                    "entry_name": "George #1",
                    "paid": "TRUE",
                    "amount_paid": "500",
                    "created_at": "",
                    "active": "TRUE",
                },
                {
                    "entry_id": "e2",
                    "user_id": "u1",
                    "entry_name": "George #2",
                    "paid": "TRUE",
                    "amount_paid": "500",
                    "created_at": "",
                    "active": "TRUE",
                },
            ]
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
                },
                {
                    "prediction_id": "p2",
                    "entry_id": "e2",
                    "match_id": "m1",
                    "selected_result": "HOME_WIN",
                    "pred_home_goals": "1",
                    "pred_away_goals": "0",
                    "points": "3",
                    "submitted_at": "",
                },
            ]
        )
        results = pd.DataFrame([{"match_id": "m1", "home_score": "2", "away_score": "1", "updated_at": ""}])

        rankings = build_rankings(entries, users, predictions, results)

        self.assertEqual(rankings.iloc[0]["entry_name"], "George #1")
        self.assertEqual(rankings.iloc[1]["entry_name"], "George #2")
        self.assertEqual(len(rankings), 2)


if __name__ == "__main__":
    unittest.main()
