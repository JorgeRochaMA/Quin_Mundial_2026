"""Login and registration page."""

from __future__ import annotations

import streamlit as st

from components.layout import configure_page, current_user, render_sidebar
from components.ui import info_card, metric_card, page_hero, section_header
from services.auth import AuthError, login_or_register
from services.runtime import get_repository_or_stop


configure_page("Ingreso")
repo = get_repository_or_stop()
render_sidebar()

page_hero(
    "Quiniela Mundial 2026",
    (
        "Entra con tu nickname y código de acceso para capturar predicciones, "
        "revisar tus entradas y seguir la tabla general."
    ),
    eyebrow="ACCESO A LA QUINIELA",
    pills=["72 partidos", "$200 MXN", "Máximo 5 pts", "Ranking en vivo"],
)

if current_user():
    info_card(
        f"Sesión activa: {current_user().get('nickname')}",
        "Usa el menú lateral para ir al dashboard, crear quinielas o capturar predicciones.",
        icon="✅",
        accent="green",
    )
    st.stop()

section_header("Cómo funciona", "Cuatro pasos para entrar y competir en la quiniela.")
how_cols = st.columns(4)
how_cards = [
    ("1. Entra", "Usa tu nickname y código de acceso.", "🎟️", "green"),
    ("2. Crea tu quiniela", "Puedes tener una o varias entradas activas.", "🧾", "gold"),
    ("3. Predice", "Captura marcadores antes del bloqueo.", "⚽", "navy"),
    ("4. Compite", "La tabla se actualiza con resultados oficiales.", "🏆", "green"),
]
for column, (title, body, icon, accent) in zip(how_cols, how_cards):
    with column:
        info_card(title, body, icon=icon, accent=accent)

section_header("Reglas rápidas", "Puntaje por partido capturado.")
rule_cols = st.columns(4)
rules = [
    ("3 pts", "Aciertas ganador, perdedor o empate.", "Resultado correcto", "gold"),
    ("+2 pts", "Bono por marcador exacto.", "Extra", "green"),
    ("5 pts", "Máximo por partido.", "Tope", "navy"),
    ("0 pts", "Predicción incorrecta.", "Sin puntos", "red"),
]
for column, (value, caption, label, accent) in zip(rule_cols, rules):
    with column:
        metric_card(label, value, caption, accent)

section_header(
    "Ingresar o registrarme",
    "Si es tu primera vez, escribe tu nickname, código y opcionalmente tu nombre completo.",
)
with st.form("login_form"):
    nickname = st.text_input("Nickname", placeholder="Ej. George")
    access_code = st.text_input("Código de acceso", type="password")
    full_name = st.text_input("Nombre completo", placeholder="Opcional si ya te registraste")
    email = st.text_input("Email", placeholder="Opcional")
    submitted = st.form_submit_button("Entrar a la quiniela", use_container_width=True)

if submitted:
    try:
        user = login_or_register(
            repo,
            nickname=nickname,
            access_code=access_code,
            full_name=full_name,
            email=email,
        )
        st.session_state["user"] = user
        st.success("Listo, ya estás dentro.")
        st.rerun()
    except (AuthError, ValueError) as exc:
        st.error(str(exc))
