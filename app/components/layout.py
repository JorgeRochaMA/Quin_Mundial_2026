"""Shared Streamlit layout helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
import streamlit as st

from components.cookies import get_remember_cookie, render_clear_remember_cookie, render_set_remember_cookie
from services.auth import restore_persistent_login, revoke_persistent_login_token
from services.runtime import get_repository_or_stop, is_demo_mode
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


def _get_query_session_token() -> str:
    """Return a persistent session token from the URL query params."""
    try:
        value = st.query_params.get("session", "")
    except Exception:
        return ""

    if isinstance(value, list):
        return str(value[0] if value else "").strip()

    return str(value or "").strip()


def _clear_query_params() -> None:
    """Clear query params without interrupting the app."""
    try:
        st.query_params.clear()
    except Exception:
        return


def build_quick_access_link(token: str) -> str:
    """Build a quick access URL with the session token in the query string."""
    try:
        current_url = st.context.url
    except Exception:
        current_url = ""

    if not current_url:
        return f"?session={token}"

    parts = urlsplit(current_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, f"session={token}", ""))


def set_authenticated_session(
    user: dict[str, Any],
    data: dict[str, pd.DataFrame] | None = None,
    session_id: str | None = None,
) -> None:
    """Store the authenticated user in Streamlit session state."""
    public_user = {
        "user_id": user.get("user_id", ""),
        "nickname": user.get("nickname", ""),
        "role": user.get("role", ""),
        "active": user.get("active", True),
    }

    st.session_state["authenticated"] = True
    st.session_state["user_id"] = public_user["user_id"]
    st.session_state["nickname"] = public_user["nickname"]
    st.session_state["role"] = public_user["role"]
    st.session_state["user"] = public_user

    if session_id:
        st.session_state["persistent_session_id"] = session_id

    if data is not None:
        entries = user_entries(data, public_user["user_id"])
        if not entries.empty:
            current = st.session_state.get("active_entry_id")
            ids = entries["entry_id"].tolist()
            if current not in ids:
                st.session_state["active_entry_id"] = ids[0]


def current_user() -> dict[str, Any] | None:
    """Return the logged-in user from session state or a valid persistent cookie."""
    if st.session_state.get("authenticated"):
        user = st.session_state.get("user")
        if user:
            return user

        user_id = st.session_state.get("user_id")
        nickname = st.session_state.get("nickname")
        role = st.session_state.get("role")
        if user_id and nickname and role:
            user = {
                "user_id": user_id,
                "nickname": nickname,
                "role": role,
                "active": True,
            }
            st.session_state["user"] = user
            return user

    if st.session_state.get("_persistent_login_checked"):
        return None

    st.session_state["_persistent_login_checked"] = True
    cookie_token = get_remember_cookie()
    query_token = _get_query_session_token()
    if not cookie_token and not query_token:
        return None

    repo = get_repository_or_stop()
    if cookie_token:
        restored = restore_persistent_login(repo, cookie_token)
        if restored:
            data = repo.load_data()
            set_authenticated_session(restored.user, data, restored.session_id)
            st.rerun()

        render_clear_remember_cookie()

    if not query_token:
        return None

    restored = restore_persistent_login(repo, query_token)
    if not restored:
        _clear_query_params()
        render_clear_remember_cookie()
        return None

    data = repo.load_data()
    set_authenticated_session(restored.user, data, restored.session_id)
    st.session_state["_pending_remember_token"] = query_token
    st.session_state["_pending_remember_expires_at"] = restored.expires_at
    _clear_query_params()
    st.rerun()


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
    pending_token = st.session_state.pop("_pending_remember_token", "")
    pending_expires_at = st.session_state.pop("_pending_remember_expires_at", "")
    if pending_token and pending_expires_at:
        render_set_remember_cookie(pending_token, pending_expires_at)

    remember_message = st.session_state.pop("_remember_login_message", "")
    quick_link = st.session_state.pop("_remember_quick_link", "")

    with st.sidebar:
        if user:
            st.page_link("pages/1_Ranking_En_Vivo.py", label="Ranking en vivo")
            st.page_link("pages/2_Estadisticas.py", label="Estadísticas")
            st.page_link("pages/3_Mis_Entradas.py", label="Mis Entradas")
            st.page_link("pages/4_Quinielas_De_Todos.py", label="Quinielas de todos")
            st.page_link("pages/5_Empieza_A_Jugar.py", label="Empieza A Jugar")
            if user.get("role") == ROLE_ADMIN:
                st.page_link("pages/6_Admin.py", label="Admin")

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

        if remember_message:
            st.success(remember_message)
        if quick_link:
            st.caption("Guarda este enlace para entrar directo desde este dispositivo.")
            st.markdown(f"[Abrir enlace de acceso rápido]({quick_link})")

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
            repo = get_repository_or_stop()
            session_id = st.session_state.get("persistent_session_id")
            token = get_remember_cookie()
            if session_id:
                repo.revoke_session(session_id)
            if token:
                revoke_persistent_login_token(repo, token)
            render_clear_remember_cookie()
            _clear_query_params()
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
