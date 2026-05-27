"""Tests for scoring rules."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from utils.constants import DRAW, HOME_WIN
from utils.scoring import calculate_prediction_points, result_from_score


class ScoringTest(unittest.TestCase):
    def test_result_from_score(self) -> None:
        self.assertEqual(result_from_score(2, 1), HOME_WIN)
        self.assertEqual(result_from_score(1, 1), DRAW)

    def test_exact_score_gets_five_points(self) -> None:
        points = calculate_prediction_points(HOME_WIN, 2, 1, 2, 1)
        self.assertEqual(points, 5)

    def test_correct_result_gets_three_points(self) -> None:
        points = calculate_prediction_points(HOME_WIN, 1, 0, 2, 1)
        self.assertEqual(points, 3)

    def test_wrong_result_gets_zero_points(self) -> None:
        points = calculate_prediction_points(DRAW, 1, 1, 2, 1)
        self.assertEqual(points, 0)


if __name__ == "__main__":
    unittest.main()
