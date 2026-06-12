"""Login and registration page."""

from __future__ import annotations

from textwrap import dedent

import streamlit as st

from components.cookies import render_set_remember_cookie
from components.layout import configure_page, current_user, render_sidebar, set_authenticated_session
from components.ui import page_hero, section_header
from services.auth import AuthError, create_persistent_login_session, login_or_register
from services.runtime import get_repository_or_stop
from utils.constants import ROLE_ADMIN


configure_page("Ingreso")
repo = get_repository_or_stop()
render_sidebar()

if current_user():
    st.switch_page("pages/1_Ranking_En_Vivo.py")

page_hero(
    "Quiniela Mundial 2026",
    (
        "Entra con tu nickname y código de acceso para capturar predicciones, "
        "revisar tus entradas y seguir la tabla general."
    ),
    eyebrow="ACCESO A LA QUINIELA",
    pills=["72 partidos", "$200 MXN", "Máximo 5 pts", "Ranking en vivo"],
)

section_header("Cómo funciona", "Lo esencial para entrar y empezar.")
st.markdown(
    dedent(
        """
    <section class="qm-compact-panel qm-rules-panel qm-login-compact-panel">
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🎟️</span>
            <span><strong>Entra</strong><small>Con tu nickname y código</small></span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🧾</span>
            <span><strong>Crea quinielas</strong><small>Una o varias entradas</small></span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">⚽</span>
            <span><strong>Predice</strong><small>Captura tus marcadores</small></span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🏆</span>
            <span><strong>Compite</strong><small>En el ranking general</small></span>
        </div>
    </section>
    """
    ).strip(),
    unsafe_allow_html=True,
)

section_header("Puntuación", "Reglas rápidas por partido.")
st.markdown(
    dedent(
        """
    <section class="qm-compact-panel qm-rules-panel qm-login-compact-panel qm-login-score-panel">
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">✅</span>
            <span><strong>3 pts</strong><small>Resultado correcto</small></span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🎯</span>
            <span><strong>+2 pts</strong><small>Marcador exacto</small></span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🏆</span>
            <span><strong>5 pts</strong><small>Máximo por partido</small></span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">❌</span>
            <span><strong>0 pts</strong><small>Incorrecto</small></span>
        </div>
    </section>
    """
    ).strip(),
    unsafe_allow_html=True,
)

section_header(
    "Ingresar o registrarme",
    "Si es tu primera vez, escribe tu nickname, código y define tu contraseña personal.",
)
with st.form("login_form"):
    nickname = st.text_input("Nickname", placeholder="Ej. George")
    access_code = st.text_input("Código de acceso", type="password")
    password = st.text_input("Contraseña personal", type="password")
    remember_me = st.checkbox("Recordarme en este dispositivo")
    st.caption("Por seguridad, las sesiones de administrador no se recuerdan automáticamente.")
    submitted = st.form_submit_button("Entrar a la quiniela", use_container_width=True)

if submitted:
    try:
        user = login_or_register(
            repo,
            nickname=nickname,
            access_code=access_code,
            password=password,
        )
        data = repo.load_data()
        set_authenticated_session(user, data)

        if remember_me and user.get("role") != ROLE_ADMIN:
            token, persistent_session = create_persistent_login_session(
                repo,
                user_id=user["user_id"],
                device_label="Navegador recordado",
            )
            st.session_state["persistent_session_id"] = persistent_session["session_id"]
            st.session_state["_pending_remember_token"] = token
            st.session_state["_pending_remember_expires_at"] = persistent_session["expires_at"]
            render_set_remember_cookie(token, persistent_session["expires_at"])

        st.rerun()
    except (AuthError, ValueError) as exc:
        st.error(str(exc))
