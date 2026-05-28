"""Repository layer for pool data stored in Google Sheets."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pandas as pd

from services.google_sheets import GoogleSheetsService
from utils.constants import (
    CONFIG,
    DEFAULT_CONFIG,
    ENTRIES,
    MATCHES,
    PREDICTIONS,
    RESULTS,
    SHEET_COLUMNS,
    USERS,
    ROLE_USER,
)
from utils.data import as_bool, as_int, clean_text, now_iso
from utils.scoring import calculate_prediction_points
from utils.time import is_match_locked
from utils.validation import (
    validate_display_text,
    validate_match_status,
    validate_resource_id,
    validate_score,
    validate_selected_result,
)


class PoolRepository:
    """High-level operations for the prediction pool."""

    def __init__(self, sheets: GoogleSheetsService) -> None:
        self.sheets = sheets

        # In-memory cache for the current app execution.
        # This reduces repeated Google Sheets reads inside the same Streamlit rerun.
        self._df_cache: dict[str, pd.DataFrame] = {}
        self._config_cache: dict[str, str] | None = None

    def _read_sheet(self, sheet_name: str) -> pd.DataFrame:
        """Read a worksheet with a small in-memory cache."""
        if sheet_name not in self._df_cache:
            self._df_cache[sheet_name] = self.sheets.read_dataframe(
                sheet_name,
                SHEET_COLUMNS[sheet_name],
            )

        # Return a copy so downstream transformations do not mutate cache accidentally.
        return self._df_cache[sheet_name].copy()

    def _invalidate(self, *sheet_names: str) -> None:
        """Invalidate cached sheets after writes."""
        for sheet_name in sheet_names:
            self._df_cache.pop(sheet_name, None)

        if CONFIG in sheet_names:
            self._config_cache = None

    def clear_cache(self) -> None:
        """Clear all local repository caches."""
        self._df_cache.clear()
        self._config_cache = None

    def ensure_database(self) -> None:
        """Ensure all required worksheets and default config values exist."""
        for sheet_name, columns in SHEET_COLUMNS.items():
            self.sheets.ensure_worksheet(sheet_name, columns)

        config = self.get_config()
        missing_defaults = [
            {"key": key, "value": value}
            for key, value in DEFAULT_CONFIG.items()
            if key not in config
        ]

        for record in missing_defaults:
            self.sheets.append_record(CONFIG, record, SHEET_COLUMNS[CONFIG])

        if missing_defaults:
            self._invalidate(CONFIG)

    def load_data(self) -> dict[str, pd.DataFrame]:
        """Load all app worksheets."""
        return {
            sheet_name: self._read_sheet(sheet_name)
            for sheet_name in SHEET_COLUMNS
        }

    def get_config(self) -> dict[str, str]:
        """Return CONFIG as a dictionary."""
        if self._config_cache is not None:
            return self._config_cache.copy()

        df = self._read_sheet(CONFIG)

        if df.empty:
            self._config_cache = {}
            return {}

        self._config_cache = {
            clean_text(row["key"]): clean_text(row["value"])
            for _, row in df.iterrows()
            if clean_text(row.get("key"))
        }

        return self._config_cache.copy()

    def update_config_values(self, values: dict[str, str]) -> None:
        """Create or update CONFIG values."""
        for key, value in values.items():
            self.sheets.upsert_record(
                CONFIG,
                {"key": clean_text(key), "value": clean_text(value)},
                SHEET_COLUMNS[CONFIG],
                ["key"],
            )

        self._invalidate(CONFIG)

    def find_user_by_nickname(self, nickname: str) -> dict[str, Any] | None:
        """Find an active user by nickname."""
        users = self._read_sheet(USERS)

        if users.empty:
            return None

        normalized = clean_text(nickname).lower()
        matches = users[users["nickname"].str.strip().str.lower() == normalized]

        if matches.empty:
            return None

        user = matches.iloc[0].to_dict()
        return user if as_bool(user.get("active", "TRUE")) else None

    def create_user(
        self,
        nickname: str,
        full_name: str = "",
        email: str = "",
        role: str = ROLE_USER,
    ) -> dict[str, Any]:
        """Create a user row and return the new user."""
        nickname = validate_display_text(nickname, "nickname", 40)

        user = {
            "user_id": uuid4().hex[:12],
            "full_name": clean_text(full_name)[:120] or nickname,
            "nickname": nickname,
            "email": clean_text(email)[:120],
            "role": role,
            "active": True,
        }

        self.sheets.append_record(USERS, user, SHEET_COLUMNS[USERS])
        self._invalidate(USERS)

        return user

    def update_user_role(self, user_id: str, role: str) -> None:
        """Promote or demote a user role."""
        user_id = validate_resource_id(user_id, "user_id")

        users = self._read_sheet(USERS)

        if users.empty:
            return

        match = users[users["user_id"] == user_id]

        if match.empty:
            return

        user = match.iloc[0].to_dict()
        user["role"] = role

        self.sheets.upsert_record(USERS, user, SHEET_COLUMNS[USERS], ["user_id"])
        self._invalidate(USERS)

    def create_entry(self, user_id: str, entry_name: str) -> dict[str, Any]:
        """Create a prediction entry for a user."""
        user_id = validate_resource_id(user_id, "user_id")
        entry_name = validate_display_text(entry_name, "entry_name", 80)

        config = self.get_config()
        entry_fee = as_int(config.get("entry_fee"), 200)

        entry = {
            "entry_id": uuid4().hex[:12],
            "user_id": user_id,
            "entry_name": entry_name,
            "paid": True,
            "amount_paid": entry_fee,
            "created_at": now_iso(),
            "active": True,
        }

        self.sheets.append_record(ENTRIES, entry, SHEET_COLUMNS[ENTRIES])
        self._invalidate(ENTRIES)

        return entry

    def update_entry_payment(self, entry_id: str, paid: bool, amount_paid: int) -> None:
        """Update payment status for an entry."""
        entry_id = validate_resource_id(entry_id, "entry_id")
        amount_paid = max(0, as_int(amount_paid, 0))

        entries = self._read_sheet(ENTRIES)
        match = entries[entries["entry_id"] == entry_id]

        if match.empty:
            return

        entry = match.iloc[0].to_dict()
        entry["paid"] = paid
        entry["amount_paid"] = amount_paid

        self.sheets.upsert_record(ENTRIES, entry, SHEET_COLUMNS[ENTRIES], ["entry_id"])
        self._invalidate(ENTRIES)
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry and all predictions linked to it."""
        entry_id = validate_resource_id(entry_id, "entry_id")

        entries = self._read_sheet(ENTRIES)

        if entries.empty:
            return False

        entry_exists = not entries[entries["entry_id"] == entry_id].empty

        if not entry_exists:
            return False

        updated_entries = entries[entries["entry_id"] != entry_id].to_dict("records")

        predictions = self._read_sheet(PREDICTIONS)
        updated_predictions: list[dict[str, Any]] = []

        if not predictions.empty:
            updated_predictions = predictions[predictions["entry_id"] != entry_id].to_dict("records")

        self.sheets.replace_records(ENTRIES, updated_entries, SHEET_COLUMNS[ENTRIES])
        self.sheets.replace_records(PREDICTIONS, updated_predictions, SHEET_COLUMNS[PREDICTIONS])

        self._invalidate(ENTRIES, PREDICTIONS)

        return True

    def upsert_prediction(
        self,
        entry_id: str,
        match_id: str,
        selected_result: str,
        pred_home_goals: int,
        pred_away_goals: int,
    ) -> None:
        """Create or update a prediction before match lock."""
        entry_id = validate_resource_id(entry_id, "entry_id")
        match_id = validate_resource_id(match_id, "match_id")
        selected_result = validate_selected_result(selected_result)
        pred_home_goals = validate_score(pred_home_goals, "home goals")
        pred_away_goals = validate_score(pred_away_goals, "away goals")

        config = self.get_config()

        matches = self._read_sheet(MATCHES)
        match = matches[matches["match_id"] == match_id] if not matches.empty else pd.DataFrame()

        if match.empty:
            raise ValueError("Partido inválido.")

        if is_match_locked(match.iloc[0].to_dict(), config):
            raise ValueError("Las predicciones de este partido están bloqueadas.")

        results = self._read_sheet(RESULTS)
        result = results[results["match_id"] == match_id] if not results.empty else pd.DataFrame()

        points = 0

        if not result.empty:
            row = result.iloc[0]
            points = calculate_prediction_points(
                selected_result,
                pred_home_goals,
                pred_away_goals,
                row.get("home_score"),
                row.get("away_score"),
                as_int(config.get("points_result"), 3),
                as_int(config.get("points_exact"), 2),
            )

        predictions = self._read_sheet(PREDICTIONS)

        existing = pd.DataFrame()
        if not predictions.empty:
            existing = predictions[
                (predictions["entry_id"] == entry_id)
                & (predictions["match_id"] == match_id)
            ]

        prediction_id = existing.iloc[0]["prediction_id"] if not existing.empty else uuid4().hex[:12]

        record = {
            "prediction_id": prediction_id,
            "entry_id": entry_id,
            "match_id": match_id,
            "selected_result": selected_result,
            "pred_home_goals": pred_home_goals,
            "pred_away_goals": pred_away_goals,
            "points": points,
            "submitted_at": now_iso(),
        }

        self.sheets.upsert_record(
            PREDICTIONS,
            record,
            SHEET_COLUMNS[PREDICTIONS],
            ["entry_id", "match_id"],
        )

        self._invalidate(PREDICTIONS)

    def upsert_result(self, match_id: str, home_score: int, away_score: int) -> None:
        """Create or update an official result."""
        match_id = validate_resource_id(match_id, "match_id")
        home_score = validate_score(home_score, "home score")
        away_score = validate_score(away_score, "away score")

        matches = self._read_sheet(MATCHES)

        if matches.empty or matches[matches["match_id"] == match_id].empty:
            raise ValueError("Partido inválido.")

        record = {
            "match_id": match_id,
            "home_score": home_score,
            "away_score": away_score,
            "updated_at": now_iso(),
        }

        self.sheets.upsert_record(RESULTS, record, SHEET_COLUMNS[RESULTS], ["match_id"])
        self._invalidate(RESULTS)

    def update_match_status(self, match_id: str, status: str) -> None:
        """Update a match status."""
        match_id = validate_resource_id(match_id, "match_id")
        status = validate_match_status(status)

        matches = self._read_sheet(MATCHES)
        match = matches[matches["match_id"] == match_id]

        if match.empty:
            return

        record = match.iloc[0].to_dict()
        record["status"] = status

        self.sheets.upsert_record(MATCHES, record, SHEET_COLUMNS[MATCHES], ["match_id"])
        self._invalidate(MATCHES)

    def recalculate_prediction_points(self) -> int:
        """Recalculate all prediction points from official results."""
        config = self.get_config()
        predictions = self._read_sheet(PREDICTIONS)
        results = self._read_sheet(RESULTS)

        if predictions.empty:
            return 0

        result_map = {
            row["match_id"]: row.to_dict()
            for _, row in results.iterrows()
            if clean_text(row.get("match_id"))
        }

        updated_records: list[dict[str, Any]] = []

        for _, prediction in predictions.iterrows():
            record = prediction.to_dict()
            result = result_map.get(record.get("match_id"))

            if result:
                record["points"] = calculate_prediction_points(
                    record.get("selected_result"),
                    record.get("pred_home_goals"),
                    record.get("pred_away_goals"),
                    result.get("home_score"),
                    result.get("away_score"),
                    as_int(config.get("points_result"), 3),
                    as_int(config.get("points_exact"), 2),
                )
            else:
                record["points"] = 0

            updated_records.append(record)

        self.sheets.replace_records(PREDICTIONS, updated_records, SHEET_COLUMNS[PREDICTIONS])
        self._invalidate(PREDICTIONS)

        return len(updated_records)