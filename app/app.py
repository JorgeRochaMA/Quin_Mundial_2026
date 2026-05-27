"""Login and registration page."""

from __future__ import annotations

import streamlit as st

from components.layout import configure_page, current_user, render_sidebar
from services.auth import AuthError, login_or_register
from services.runtime import get_repository_or_stop


configure_page("Ingreso")
repo = get_repository_or_stop()
render_sidebar()

st.title("Ingreso")
st.write("Usa tu nickname y el código de acceso de la quiniela.")

if current_user():
    st.success(f"Sesión activa: {current_user().get('nickname')}")
    st.info("Usa el menú lateral para ir al dashboard, crear quinielas o capturar predicciones.")
    st.stop()

with st.form("login_form"):
    nickname = st.text_input("Nickname", placeholder="Ej. George")
    access_code = st.text_input("Código de acceso", type="password")
    full_name = st.text_input("Nombre completo", placeholder="Opcional si ya te registraste")
    email = st.text_input("Email", placeholder="Opcional")
    submitted = st.form_submit_button("Entrar", use_container_width=True)

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
