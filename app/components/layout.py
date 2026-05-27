"""Shared Streamlit layout helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from services.runtime import is_demo_mode
from utils.constants import ENTRIES, ROLE_ADMIN
from utils.data import as_bool


def load_css() -> None:
    """Load shared app styles from the assets directory."""
    css_path = Path(__file__).resolve().parents[1] / "assets" / "styles.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def configure_page(title: str) -> None:
    """Apply page config and shared CSS."""
    st.set_page_config(
        page_title=f"{title} | Quiniela Mundial 2026",
        page_icon="🏆",
        layout="wide",
    )
    load_css()


def current_user() -> dict[str, Any] | None:
    """Return the logged-in user from session state."""
    return st.session_state.get("user")


def require_login() -> dict[str, Any]:
    """Stop the page when no user is logged in."""
    user = current_user()
    if not user:
        st.warning("Inicia sesión para continuar.")
        st.stop()
    return user


def require_admin() -> dict[str, Any]:
    """Stop the page when the current user is not an admin."""
    user = require_login()
    if user.get("role") != ROLE_ADMIN:
        st.error("Esta sección es solo para administradores.")
        st.stop()
    return user


def user_entries(data: dict[str, pd.DataFrame], user_id: str) -> pd.DataFrame:
    """Return active entries for one user."""
    entries = data.get(ENTRIES, pd.DataFrame())
    if entries.empty:
        return entries
    filtered = entries[(entries["user_id"] == user_id) & (entries["active"].apply(as_bool))]
    return filtered.reset_index(drop=True)


def render_sidebar(data: dict[str, pd.DataFrame] | None = None) -> None:
    """Render session details, entry selector, and logout."""
    user = current_user()
    with st.sidebar:
        st.markdown(
            """
            <div class="qm-brand">
                <span class="qm-brand-mark">🏆</span>
                <span>
                    <span class="qm-brand-title">Quiniela Mundial</span>
                    <span class="qm-brand-year">2026</span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if is_demo_mode():
            st.info("Modo demo local")
        if not user:
            st.info("Sin sesión activa")
            return

        st.caption(f"👤 {user.get('nickname', '')}")
        if user.get("role") == ROLE_ADMIN:
            st.caption("🛡️ Administrador")

        if data is not None:
            entries = user_entries(data, user.get("user_id", ""))
            if not entries.empty:
                labels = []
                ids = []
                for _, entry in entries.iterrows():
                    labels.append(f"{entry.get('entry_name')}")
                    ids.append(entry.get("entry_id"))

                current = st.session_state.get("active_entry_id")
                index = ids.index(current) if current in ids else 0
                selected = st.selectbox("🎟️ Quiniela activa", labels, index=index)
                st.session_state["active_entry_id"] = ids[labels.index(selected)]
            else:
                st.info("Aún no tienes quinielas.")

        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        if is_demo_mode() and st.button("Reiniciar demo", use_container_width=True):
            user_backup = st.session_state.get("user")
            st.session_state.clear()
            if user_backup:
                st.session_state["user"] = user_backup
            st.rerun()


def active_entry(data: dict[str, pd.DataFrame]) -> dict[str, Any] | None:
    """Return the selected entry from session state."""
    entry_id = st.session_state.get("active_entry_id")
    entries = data.get(ENTRIES, pd.DataFrame())
    if not entry_id or entries.empty:
        return None
    match = entries[entries["entry_id"] == entry_id]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def spanish_bool(value: Any) -> str:
    """Render a boolean-like spreadsheet value in Spanish."""
    return "Sí" if as_bool(value) else "No"
