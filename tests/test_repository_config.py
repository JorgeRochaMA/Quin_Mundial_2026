"""Tests for repository configuration updates."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

gspread_module = types.ModuleType("gspread")
gspread_exceptions = types.ModuleType("gspread.exceptions")
gspread_utils = types.ModuleType("gspread.utils")
gspread_exceptions.WorksheetNotFound = type("WorksheetNotFound", (Exception,), {})
gspread_utils.rowcol_to_a1 = lambda row, col: f"R{row}C{col}"
gspread_module.exceptions = gspread_exceptions
gspread_module.utils = gspread_utils
gspread_module.service_account_from_dict = lambda credentials: None
sys.modules.setdefault("gspread", gspread_module)
sys.modules.setdefault("gspread.exceptions", gspread_exceptions)
sys.modules.setdefault("gspread.utils", gspread_utils)

from services.pool_repository import PoolRepository
from utils.constants import CONFIG, SHEET_COLUMNS


class FakeSheetsService:
    def __init__(self) -> None:
        self.records: dict[str, str] = {}

    def read_dataframe(self, title: str, columns: list[str]) -> pd.DataFrame:
        if title != CONFIG:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(
            [{"key": key, "value": value} for key, value in self.records.items()],
            columns=SHEET_COLUMNS[CONFIG],
        )

    def upsert_record(
        self,
        title: str,
        record: dict[str, Any],
        columns: list[str],
        key_columns: list[str],
    ) -> None:
        self.records[str(record["key"])] = str(record["value"])


class RepositoryConfigTest(unittest.TestCase):
    def test_update_config_values_upserts_config_rows(self) -> None:
        sheets = FakeSheetsService()
        repo = PoolRepository(sheets)  # type: ignore[arg-type]

        repo.update_config_values(
            {
                "entry_fee": "250",
                "first_place_percentage": "0.70",
            }
        )

        self.assertEqual(repo.get_config()["entry_fee"], "250")
        self.assertEqual(repo.get_config()["first_place_percentage"], "0.70")


if __name__ == "__main__":
    unittest.main()
