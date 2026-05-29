"""Predictions page."""

from __future__ import annotations

import streamlit as st

from components.layout import active_entry, configure_page, render_sidebar, require_login
from components.predictions_capture import render_predictions_capture
from components.ui import empty_state, page_hero
from services.runtime import get_repository_or_stop


configure_page("Predicciones")
require_login()

repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()

render_sidebar(data)

entry = active_entry(data)

if not entry:
    page_hero(
        "Predicciones",
        "Primero crea o selecciona una quiniela para capturar marcadores.",
        eyebrow="Captura de resultados",
        pills=["Sin quiniela activa"],
    )
    empty_state(
        "No hay quiniela activa",
        "Primero crea o selecciona una quiniela en la sección Mis quinielas.",
        icon="🎟️",
    )
    st.stop()

render_predictions_capture(
    entry=entry,
    data=data,
    config=config,
    repo=repo,
    title="Predicciones",
    subtitle="Captura tus marcadores para la fase de grupos.",
    eyebrow="Captura de resultados",
    show_hero=True,
)
