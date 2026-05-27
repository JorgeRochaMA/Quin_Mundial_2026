"""Runtime helpers for Streamlit pages."""

from __future__ import annotations

import logging
import os
from typing import Any

import streamlit as st

from services.demo_repository import DemoPoolRepository
from services.google_sheets import GoogleSheetsConfigError, GoogleSheetsService
from services.pool_repository import PoolRepository

LOGGER = logging.getLogger(__name__)


def _read_secret_section(name: str) -> dict[str, Any]:
    try:
        section = st.secrets.get(name, {})
    except Exception:
        return {}
    return dict(section) if section else {}


@st.cache_resource(show_spinner=False)
def get_google_repository() -> PoolRepository:
    """Build and cache the Google Sheets-backed repository."""
    google_sheets = _read_secret_section("google_sheets")
    spreadsheet_id = google_sheets.get("spreadsheet_id", "")
    credentials = _read_secret_section("gcp_service_account")

    if not spreadsheet_id or not credentials:
        raise GoogleSheetsConfigError(
            "Missing Streamlit secrets. Copy .streamlit/secrets.example.toml "
            "to .streamlit/secrets.toml and fill your Google credentials."
        )

    service = GoogleSheetsService(spreadsheet_id, credentials)
    repo = PoolRepository(service)
    repo.ensure_database()
    return repo


def get_data_source() -> str:
    """Return the selected data source."""
    app_settings = _read_secret_section("app")
    data_source = os.environ.get("QUINIELA_DATA_SOURCE") or app_settings.get("data_source")
    return str(data_source or "google_sheets").strip().lower()


def is_demo_mode() -> bool:
    """Return whether the app is running with in-memory demo data."""
    return get_data_source() == "demo"


def get_repository_or_stop() -> PoolRepository | DemoPoolRepository:
    """Return the repository or stop the page with a setup-friendly error."""
    if is_demo_mode():
        return DemoPoolRepository()

    try:
        return get_google_repository()
    except Exception as exc:
        LOGGER.exception("Could not initialize Google Sheets repository.")
        st.error("No se pudo conectar con Google Sheets.")
        st.info("Revisa los secretos de Streamlit y que la hoja esté compartida con el service account.")
        st.caption("Los detalles técnicos del error se mantienen ocultos por seguridad.")
        st.stop()
