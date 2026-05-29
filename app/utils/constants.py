"""Application constants and Google Sheets schema definitions."""

CONFIG = "CONFIG"
USERS = "USERS"
ENTRIES = "ENTRIES"
MATCHES = "MATCHES"
RESULTS = "RESULTS"
PREDICTIONS = "PREDICTIONS"

ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"

STATUS_OPEN = "OPEN"
STATUS_LOCKED = "LOCKED"
STATUS_FINISHED = "FINISHED"
MATCH_STATUSES = [STATUS_OPEN, STATUS_LOCKED, STATUS_FINISHED]

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"
DRAW = "DRAW"
RESULT_VALUES = [HOME_WIN, DRAW, AWAY_WIN]

SHEET_COLUMNS = {
    CONFIG: ["key", "value"],
    USERS: ["user_id", "full_name", "nickname", "email", "role", "active", "password_hash"],
    ENTRIES: [
        "entry_id",
        "user_id",
        "entry_name",
        "paid",
        "amount_paid",
        "created_at",
        "active",
    ],
    MATCHES: [
        "match_id",
        "stage",
        "group",
        "match_date",
        "home_team",
        "away_team",
        "stadium",
        "city",
        "status",
    ],
    RESULTS: ["match_id", "home_score", "away_score", "updated_at"],
    PREDICTIONS: [
        "prediction_id",
        "entry_id",
        "match_id",
        "selected_result",
        "pred_home_goals",
        "pred_away_goals",
        "points",
        "submitted_at",
    ],
}

DEFAULT_CONFIG = {
    "entry_fee": "200",
    "points_result": "3",
    "points_exact": "2",
    "first_place_percentage": "0.60",
    "second_place_percentage": "0.30",
    "third_place_percentage": "0.10",
    "lock_minutes_before_match": "60",
    "predictions_lock_at": "2026-06-10 23:59",
    "current_phase_label": "Fase de grupos",
    "current_phase_total_matches": "72",
    "current_phase_groups": "12",
    "pool_access_code": "",
    "admin_access_code": "",
    "timezone": "America/Mexico_City",
}

DISPLAY_RESULT_LABELS = {
    HOME_WIN: "Gana local",
    DRAW: "Empate",
    AWAY_WIN: "Gana visitante",
}
