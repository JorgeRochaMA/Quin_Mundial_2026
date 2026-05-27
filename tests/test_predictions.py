"""Tests for prediction summaries."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from utils.constants import MATCHES, PREDICTIONS, SHEET_COLUMNS
from utils.predictions import build_entry_prediction_summary


class PredictionSummaryTest(unittest.TestCase):
    def test_summary_is_entry_specific_and_ordered_by_date(self) -> None:
        matches = pd.DataFrame(
            [
                {
                    "match_id": "m2",
                    "stage": "Group Stage",
                    "group": "B",
                    "match_date": "2026-06-12 13:00",
                    "home_team": "Canada",
                    "away_team": "Bosnia",
                    "stadium": "",
                    "city": "",
                    "status": "OPEN",
                },
                {
                    "match_id": "m1",
                    "stage": "Group Stage",
                    "group": "A",
                    "match_date": "2026-06-11 13:00",
                    "home_team": "Mexico",
                    "away_team": "South Africa",
                    "stadium": "",
                    "city": "",
                    "status": "OPEN",
                },
            ],
            columns=SHEET_COLUMNS[MATCHES],
        )
        predictions = pd.DataFrame(
            [
                {
                    "prediction_id": "p1",
                    "entry_id": "e1",
                    "match_id": "m1",
                    "selected_result": "DRAW",
                    "pred_home_goals": "1",
                    "pred_away_goals": "1",
                    "points": "0",
                    "submitted_at": "",
                },
                {
                    "prediction_id": "p2",
                    "entry_id": "e2",
                    "match_id": "m1",
                    "selected_result": "HOME_WIN",
                    "pred_home_goals": "2",
                    "pred_away_goals": "0",
                    "points": "0",
                    "submitted_at": "",
                },
            ],
            columns=SHEET_COLUMNS[PREDICTIONS],
        )

        summary = build_entry_prediction_summary(matches, predictions, "e1")

        self.assertEqual(summary.iloc[0]["match_date"], "2026-06-11 13:00")
        self.assertEqual(summary.iloc[0]["selected_result_label"], "Empate")
        self.assertEqual(summary.iloc[0]["prediction"], "1 - 1")
        self.assertEqual(summary.iloc[1]["capture_status"], "Pendiente")


if __name__ == "__main__":
    unittest.main()
