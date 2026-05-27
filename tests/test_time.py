"""Tests for match locking rules."""

from __future__ import annotations

import unittest

from utils.constants import STATUS_OPEN
from utils.time import is_match_locked


class TimeLockingTest(unittest.TestCase):
    def test_global_prediction_lock_blocks_open_matches(self) -> None:
        match = {
            "status": STATUS_OPEN,
            "match_date": "2999-01-01 20:00",
        }
        config = {
            "predictions_lock_at": "2000-01-01 00:00",
            "lock_minutes_before_match": "60",
        }

        self.assertTrue(is_match_locked(match, config))

    def test_future_global_prediction_lock_keeps_future_match_open(self) -> None:
        match = {
            "status": STATUS_OPEN,
            "match_date": "2999-01-01 20:00",
        }
        config = {
            "predictions_lock_at": "2998-12-01 00:00",
            "lock_minutes_before_match": "60",
        }

        self.assertFalse(is_match_locked(match, config))


if __name__ == "__main__":
    unittest.main()
