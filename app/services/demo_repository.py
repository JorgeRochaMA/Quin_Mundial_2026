"""In-memory repository for local design previews."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pandas as pd
import streamlit as st

from utils.constants import (
    CONFIG,
    DEFAULT_CONFIG,
    ENTRIES,
    MATCHES,
    PREDICTIONS,
    RESULTS,
    ROLE_ADMIN,
    ROLE_USER,
    SHEET_COLUMNS,
    STATUS_FINISHED,
    STATUS_LOCKED,
    STATUS_OPEN,
    USERS,
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

DEMO_STORAGE_KEY = "demo_repository_data"


class DemoPoolRepository:
    """A Google Sheets-compatible repository backed by Streamlit session state."""

    def __init__(self) -> None:
        self.ensure_database()

    def ensure_database(self) -> None:
        """Initialize demo data once per browser session."""
        if DEMO_STORAGE_KEY not in st.session_state:
            st.session_state[DEMO_STORAGE_KEY] = _build_seed_data()

    def load_data(self) -> dict[str, pd.DataFrame]:
        """Load all demo tables."""
        self.ensure_database()
        return {
            sheet_name: df.copy()
            for sheet_name, df in st.session_state[DEMO_STORAGE_KEY].items()
        }

    def get_config(self) -> dict[str, str]:
        """Return demo CONFIG as a dictionary."""
        config = self._df(CONFIG)
        return {
            clean_text(row["key"]): clean_text(row["value"])
            for _, row in config.iterrows()
            if clean_text(row.get("key"))
        }

    def update_config_values(self, values: dict[str, str]) -> None:
        """Create or update demo CONFIG values."""
        for key, value in values.items():
            self._upsert(
                CONFIG,
                {"key": clean_text(key), "value": clean_text(value)},
                ["key"],
            )

    def find_user_by_nickname(self, nickname: str) -> dict[str, Any] | None:
        """Find an active demo user by nickname."""
        users = self._df(USERS)
        normalized = clean_text(nickname).lower()
        matches = users[users["nickname"].str.strip().str.lower() == normalized]
        if matches.empty:
            return None
        user = matches.iloc[0].to_dict()
        return user if as_bool(user.get("active", "TRUE")) else None

    def list_active_user_nicknames(self) -> list[str]:
        """Return nicknames for active demo users."""
        users = self._df(USERS)
        if users.empty:
            return []
        active_users = users[users["active"].apply(as_bool)] if "active" in users else users
        return [
            clean_text(row.get("nickname"))
            for _, row in active_users.iterrows()
            if clean_text(row.get("nickname"))
        ]

    def create_user(
        self,
        nickname: str,
        full_name: str = "",
        email: str = "",
        role: str = ROLE_USER,
        password_hash: str = "",
    ) -> dict[str, Any]:
        """Create a demo user row."""
        nickname = validate_display_text(nickname, "nickname", 40)
        user = {
            "user_id": uuid4().hex[:12],
            "full_name": clean_text(full_name)[:120] or nickname,
            "nickname": nickname,
            "email": clean_text(email)[:120],
            "role": role,
            "active": True,
            "password_hash": clean_text(password_hash),
        }
        self._append(USERS, user)
        return user

    def update_user_password_hash(self, user_id: str, password_hash: str) -> None:
        """Set or replace the stored password hash for a demo user."""
        user_id = validate_resource_id(user_id, "user_id")
        users = self._df(USERS)
        match = users[users["user_id"] == user_id]
        if match.empty:
            return
        user = match.iloc[0].to_dict()
        user["password_hash"] = clean_text(password_hash)
        self._upsert(USERS, user, ["user_id"])

    def update_user_role(self, user_id: str, role: str) -> None:
        """Promote or demote a demo user."""
        user_id = validate_resource_id(user_id, "user_id")
        users = self._df(USERS)
        match = users[users["user_id"] == user_id]
        if match.empty:
            return
        user = match.iloc[0].to_dict()
        user["role"] = role
        self._upsert(USERS, user, ["user_id"])

    def create_entry(self, user_id: str, entry_name: str) -> dict[str, Any]:
        """Create a demo prediction entry."""
        user_id = validate_resource_id(user_id, "user_id")
        entry_name = validate_display_text(entry_name, "entry_name", 80)
        entry_fee = as_int(self.get_config().get("entry_fee"), 200)
        entry = {
            "entry_id": uuid4().hex[:12],
            "user_id": user_id,
            "entry_name": entry_name,
            "paid": True,
            "amount_paid": entry_fee,
            "created_at": now_iso(),
            "active": True,
        }
        self._append(ENTRIES, entry)
        return entry

    def update_entry_payment(self, entry_id: str, paid: bool, amount_paid: int) -> None:
        """Update payment status for a demo entry."""
        entry_id = validate_resource_id(entry_id, "entry_id")
        amount_paid = max(0, as_int(amount_paid, 0))
        entries = self._df(ENTRIES)
        match = entries[entries["entry_id"] == entry_id]
        if match.empty:
            return
        entry = match.iloc[0].to_dict()
        entry["paid"] = paid
        entry["amount_paid"] = amount_paid
        self._upsert(ENTRIES, entry, ["entry_id"])

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a demo entry and all predictions linked to it."""
        entry_id = validate_resource_id(entry_id, "entry_id")

        entries = self._df(ENTRIES)

        if entries.empty or entries[entries["entry_id"] == entry_id].empty:
            return False

        updated_entries = entries[entries["entry_id"] != entry_id].to_dict("records")

        predictions = self._df(PREDICTIONS)
        updated_predictions: list[dict[str, Any]] = []

        if not predictions.empty:
            updated_predictions = predictions[predictions["entry_id"] != entry_id].to_dict("records")

        self._replace(ENTRIES, updated_entries)
        self._replace(PREDICTIONS, updated_predictions)

        return True

    def upsert_prediction(
        self,
        entry_id: str,
        match_id: str,
        selected_result: str,
        pred_home_goals: int,
        pred_away_goals: int,
    ) -> None:
        """Create or update a demo prediction before match lock."""
        entry_id = validate_resource_id(entry_id, "entry_id")
        match_id = validate_resource_id(match_id, "match_id")
        selected_result = validate_selected_result(selected_result)
        pred_home_goals = validate_score(pred_home_goals, "home goals")
        pred_away_goals = validate_score(pred_away_goals, "away goals")

        config = self.get_config()
        matches = self._df(MATCHES)
        match = matches[matches["match_id"] == match_id]
        if match.empty:
            raise ValueError("Partido inválido.")

        results = self._df(RESULTS)
        result = results[results["match_id"] == match_id] if not results.empty else pd.DataFrame()
        official_result = None if result.empty else result.iloc[0].to_dict()

        if is_match_locked(match.iloc[0].to_dict(), config, official_result):
            raise ValueError("Las predicciones de este partido están bloqueadas.")

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

        predictions = self._df(PREDICTIONS)
        existing = predictions[
            (predictions["entry_id"] == entry_id) & (predictions["match_id"] == match_id)
        ]
        prediction_id = existing.iloc[0]["prediction_id"] if not existing.empty else uuid4().hex[:12]
        self._upsert(
            PREDICTIONS,
            {
                "prediction_id": prediction_id,
                "entry_id": entry_id,
                "match_id": match_id,
                "selected_result": selected_result,
                "pred_home_goals": pred_home_goals,
                "pred_away_goals": pred_away_goals,
                "points": points,
                "submitted_at": now_iso(),
            },
            ["entry_id", "match_id"],
        )

    def upsert_result(self, match_id: str, home_score: int, away_score: int) -> None:
        """Create or update a demo official result."""
        match_id = validate_resource_id(match_id, "match_id")
        home_score = validate_score(home_score, "home score")
        away_score = validate_score(away_score, "away score")
        matches = self._df(MATCHES)
        if matches.empty or matches[matches["match_id"] == match_id].empty:
            raise ValueError("Partido inválido.")

        self._upsert(
            RESULTS,
            {
                "match_id": match_id,
                "home_score": home_score,
                "away_score": away_score,
                "updated_at": now_iso(),
            },
            ["match_id"],
        )

    def update_match_status(self, match_id: str, status: str) -> None:
        """Update a demo match status."""
        match_id = validate_resource_id(match_id, "match_id")
        status = validate_match_status(status)
        matches = self._df(MATCHES)
        match = matches[matches["match_id"] == match_id]
        if match.empty:
            return
        record = match.iloc[0].to_dict()
        record["status"] = status
        self._upsert(MATCHES, record, ["match_id"])

    def recalculate_prediction_points(self) -> int:
        """Recalculate all demo prediction points from official results."""
        config = self.get_config()
        predictions = self._df(PREDICTIONS)
        results = self._df(RESULTS)
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

        self._replace(PREDICTIONS, updated_records)
        return len(updated_records)

    def reset_demo_data(self) -> None:
        """Reset demo data for the current browser session."""
        st.session_state[DEMO_STORAGE_KEY] = _build_seed_data()

    def _df(self, sheet_name: str) -> pd.DataFrame:
        return st.session_state[DEMO_STORAGE_KEY][sheet_name].copy()

    def _append(self, sheet_name: str, record: dict[str, Any]) -> None:
        df = self._df(sheet_name)
        columns = SHEET_COLUMNS[sheet_name]
        row = {column: record.get(column, "") for column in columns}
        st.session_state[DEMO_STORAGE_KEY][sheet_name] = pd.concat(
            [df, pd.DataFrame([row], columns=columns)],
            ignore_index=True,
        )

    def _upsert(self, sheet_name: str, record: dict[str, Any], key_columns: list[str]) -> None:
        df = self._df(sheet_name)
        columns = SHEET_COLUMNS[sheet_name]
        if df.empty:
            self._append(sheet_name, record)
            return

        mask = pd.Series([True] * len(df))
        for key in key_columns:
            mask = mask & (df[key].astype(str) == str(record.get(key, "")))

        if mask.any():
            for column in columns:
                df.loc[mask, column] = record.get(column, "")
            st.session_state[DEMO_STORAGE_KEY][sheet_name] = df
        else:
            self._append(sheet_name, record)

    def _replace(self, sheet_name: str, records: list[dict[str, Any]]) -> None:
        columns = SHEET_COLUMNS[sheet_name]
        st.session_state[DEMO_STORAGE_KEY][sheet_name] = pd.DataFrame(records, columns=columns)


def _build_seed_data() -> dict[str, pd.DataFrame]:
    config = DEFAULT_CONFIG | {
        "pool_access_code": "demo-user",
        "admin_access_code": "demo-admin",
        "entry_fee": "200",
    }

    data = {
        CONFIG: pd.DataFrame(
            [{"key": key, "value": value} for key, value in config.items()],
            columns=SHEET_COLUMNS[CONFIG],
        ),
        USERS: pd.DataFrame(
            [
                {
                    "user_id": "u_demo_george",
                    "full_name": "George Demo",
                    "nickname": "George",
                    "email": "george@example.com",
                    "role": ROLE_USER,
                    "active": True,
                    "password_hash": "",
                },
                {
                    "user_id": "u_demo_admin",
                    "full_name": "Admin Demo",
                    "nickname": "Admin",
                    "email": "admin@example.com",
                    "role": ROLE_ADMIN,
                    "active": True,
                    "password_hash": "",
                },
            ],
            columns=SHEET_COLUMNS[USERS],
        ),
        ENTRIES: pd.DataFrame(
            [
                {
                    "entry_id": "e_demo_george_1",
                    "user_id": "u_demo_george",
                    "entry_name": "George #1",
                    "paid": True,
                    "amount_paid": "200",
                    "created_at": "2026-05-01 10:00",
                    "active": True,
                },
                {
                    "entry_id": "e_demo_george_2",
                    "user_id": "u_demo_george",
                    "entry_name": "George #2",
                    "paid": True,
                    "amount_paid": "200",
                    "created_at": "2026-05-01 10:05",
                    "active": True,
                },
            ],
            columns=SHEET_COLUMNS[ENTRIES],
        ),
        MATCHES: pd.DataFrame(
            [
                {
                    "match_id": "M001",
                    "stage": "Group Stage",
                    "group": "A",
                    "match_date": "2026-06-11 20:00",
                    "home_team": "Mexico",
                    "away_team": "Japan",
                    "stadium": "Stadium TBD",
                    "city": "City TBD",
                    "status": STATUS_OPEN,
                },
                {
                    "match_id": "M002",
                    "stage": "Group Stage",
                    "group": "B",
                    "match_date": "2026-06-12 18:00",
                    "home_team": "Argentina",
                    "away_team": "Canada",
                    "stadium": "Stadium TBD",
                    "city": "City TBD",
                    "status": STATUS_OPEN,
                },
                {
                    "match_id": "M003",
                    "stage": "Group Stage",
                    "group": "C",
                    "match_date": "2026-06-13 18:00",
                    "home_team": "Spain",
                    "away_team": "Morocco",
                    "stadium": "Stadium TBD",
                    "city": "City TBD",
                    "status": STATUS_LOCKED,
                },
                {
                    "match_id": "M004",
                    "stage": "Group Stage",
                    "group": "D",
                    "match_date": "2026-06-14 20:00",
                    "home_team": "Brazil",
                    "away_team": "Germany",
                    "stadium": "Stadium TBD",
                    "city": "City TBD",
                    "status": STATUS_FINISHED,
                },
            ],
            columns=SHEET_COLUMNS[MATCHES],
        ),
        RESULTS: pd.DataFrame(
            [
                {
                    "match_id": "M004",
                    "home_score": "2",
                    "away_score": "1",
                    "updated_at": "2026-06-14 22:00",
                }
            ],
            columns=SHEET_COLUMNS[RESULTS],
        ),
        PREDICTIONS: pd.DataFrame(
            [
                {
                    "prediction_id": "p_demo_1",
                    "entry_id": "e_demo_george_1",
                    "match_id": "M004",
                    "selected_result": "HOME_WIN",
                    "pred_home_goals": "2",
                    "pred_away_goals": "1",
                    "points": "5",
                    "submitted_at": "2026-06-10 09:00",
                },
                {
                    "prediction_id": "p_demo_2",
                    "entry_id": "e_demo_george_2",
                    "match_id": "M004",
                    "selected_result": "HOME_WIN",
                    "pred_home_goals": "1",
                    "pred_away_goals": "0",
                    "points": "3",
                    "submitted_at": "2026-06-10 09:05",
                },
            ],
            columns=SHEET_COLUMNS[PREDICTIONS],
        ),
    }
    return data
