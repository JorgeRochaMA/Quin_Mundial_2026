"""Login and registration page."""

from __future__ import annotations

from textwrap import dedent

import streamlit as st

from components.layout import configure_page, current_user, render_sidebar
from components.ui import page_hero, section_header
from services.auth import AuthError, login_or_register
from services.runtime import get_repository_or_stop


configure_page("Ingreso")
repo = get_repository_or_stop()
render_sidebar()

if current_user():
    st.switch_page("pages/0_Empieza_A_Jugar.py")

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
    submitted = st.form_submit_button("Entrar a la quiniela", use_container_width=True)

if submitted:
    try:
        user = login_or_register(
            repo,
            nickname=nickname,
            access_code=access_code,
            password=password,
        )
        st.session_state["user"] = user
        st.success("Listo, ya estás dentro.")
        st.switch_page("pages/0_Empieza_A_Jugar.py")
    except (AuthError, ValueError) as exc:
        st.error(str(exc))
