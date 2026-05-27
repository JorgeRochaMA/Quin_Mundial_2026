"""Shared Streamlit layout helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from services.runtime import is_demo_mode
from utils.constants import ENTRIES, ROLE_ADMIN
from utils.data import as_bool


def configure_page(title: str) -> None:
    """Apply page config and shared CSS."""
    st.set_page_config(
        page_title=f"{title} | Quiniela Mundial 2026",
        page_icon="🏆",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        :root {
            --qm-brand: #087f5b;
            --qm-brand-dark: #07503f;
            --qm-brand-soft: #dff5ec;
            --qm-gold: #d49a18;
            --qm-red: #c1121f;
            --qm-text: #14213d;
        }
        .stApp {
            background:
                linear-gradient(115deg, rgba(8, 127, 91, 0.10), transparent 30%),
                linear-gradient(35deg, rgba(193, 18, 31, 0.06), transparent 34%),
                repeating-linear-gradient(90deg, rgba(8, 127, 91, 0.025) 0 2px, transparent 2px 82px),
                linear-gradient(180deg, #ffffff 0, #f4f7f5 330px);
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1100px;
        }
        h1, h2, h3 {
            color: var(--qm-text);
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.92)),
                #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
            box-shadow: 0 16px 36px rgba(20, 33, 61, 0.08);
        }
        section[data-testid="stSidebar"] {
            background:
                linear-gradient(155deg, rgba(193, 18, 31, 0.30), transparent 31%),
                linear-gradient(25deg, rgba(8, 127, 91, 0.55), transparent 52%),
                linear-gradient(180deg, #1f1020 0%, #082836 46%, #062d2c 100%);
        }
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] label {
            color: rgba(255, 255, 255, 0.76);
        }
        .qm-brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.25rem 0 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.16);
            margin-bottom: 1rem;
        }
        .qm-brand-mark {
            display: inline-grid;
            place-items: center;
            width: 2.8rem;
            height: 2.8rem;
            border-radius: 1rem;
            background:
                radial-gradient(circle at 28% 28%, rgba(255, 255, 255, 0.86), transparent 24%),
                conic-gradient(from 20deg, #087f5b, #f8fafc, #c1121f, #d49a18, #087f5b);
            box-shadow:
                inset 0 0 0 3px rgba(255, 255, 255, 0.28),
                0 14px 28px rgba(0, 0, 0, 0.22);
            font-size: 1.35rem;
        }
        .qm-brand-title {
            font-family: "Trebuchet MS", system-ui, sans-serif;
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.05;
            text-shadow: 0 2px 12px rgba(0, 0, 0, 0.26);
        }
        .qm-brand-year {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.78rem;
            font-weight: 800;
        }
        .small-muted {
            color: #64748b;
            font-size: 0.9rem;
        }
        div.stButton > button[kind="primary"],
        div.stFormSubmitButton > button {
            border: 0;
            background: linear-gradient(135deg, var(--qm-brand), var(--qm-brand-dark));
            box-shadow: 0 10px 18px rgba(8, 127, 91, 0.16);
            font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
