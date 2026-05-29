"""Main play flow page."""

from __future__ import annotations

from html import escape

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login, user_entries
from components.predictions_capture import render_predictions_capture
from components.ui import empty_state, info_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import MATCHES, PREDICTIONS, RESULTS, USERS
from utils.data import clean_text
from utils.rankings import build_rankings


configure_page("Empieza a jugar")
user = require_login()
repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

entries = user_entries(data, user["user_id"])
rankings = build_rankings(entries, data[USERS], data[PREDICTIONS], data[RESULTS])

points_by_entry = {}
if not rankings.empty:
    points_by_entry = rankings.set_index("entry_id")["total_points"].to_dict()

total_entries = len(entries)
current_entry_id = st.session_state.get("active_entry_id")
active_entry_name = "Sin quiniela activa"

if not entries.empty:
    ids = entries["entry_id"].tolist()
    if current_entry_id not in ids:
        current_entry_id = ids[0]
        st.session_state["active_entry_id"] = current_entry_id

    active_match = entries[entries["entry_id"] == current_entry_id]
    if not active_match.empty:
        active_entry_name = clean_text(active_match.iloc[0].get("entry_name")) or active_entry_name

page_hero(
    "Empieza a jugar",
    "Crea o selecciona una quiniela y captura tus marcadores desde una sola pantalla.",
    eyebrow="Flujo principal",
    pills=[
        "Crea o selecciona una quiniela",
        f"Estás llenando: {active_entry_name}",
        "Captura antes del cierre",
    ],
)

section_header(
    "Qué hacer aquí",
    "Este es el camino rápido para entrar, elegir tu quiniela y llenar predicciones.",
)
steps = st.columns(3)
with steps[0]:
    info_card(
        "1. Crea o selecciona una quiniela",
        "Cada quiniela participa de forma independiente en la tabla general.",
        icon="🎟️",
        accent="gold",
    )
with steps[1]:
    info_card(
        f"2. Estás llenando: {active_entry_name}",
        "La quiniela activa se mantiene también en el menú lateral.",
        icon="✅",
        accent="green",
    )
with steps[2]:
    info_card(
        "3. Captura tus marcadores antes del cierre",
        "Guarda o edita predicciones mientras los partidos estén abiertos.",
        icon="⚽",
        accent="navy",
    )

section_header(
    "Crea o selecciona una quiniela",
    "Puedes crear una nueva entrada o elegir cuál quieres llenar ahora.",
)

create_col, select_col = st.columns(2)

with create_col:
    info_card(
        "Crear nueva quiniela",
        "Puedes crear varias quinielas si quieres jugar con diferentes estrategias.",
        icon="🎟️",
        accent="gold",
    )

    with st.form("start_create_entry"):
        default_number = len(entries) + 1
        default_name = f"{user.get('nickname')} #{default_number}"

        entry_name = st.text_input("Nombre de la nueva quiniela", value=default_name)
        submitted = st.form_submit_button("Crear quiniela", use_container_width=True)

if submitted:
    if not entry_name.strip():
        st.error("Escribe un nombre para la quiniela.")
    else:
        try:
            entry = repo.create_entry(user["user_id"], entry_name)
            st.session_state["active_entry_id"] = entry["entry_id"]
            st.success("Quiniela creada.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

with select_col:
    info_card(
        "Quiniela activa",
        f"Estás llenando: {active_entry_name}",
        icon="✅",
        accent="green",
    )

    if entries.empty:
        empty_state(
            "Aún no tienes quinielas",
            "Crea tu primera quiniela para empezar a capturar predicciones.",
            icon="🎟️",
        )
        st.stop()

    labels = [
        f"{row['entry_name']} · {int(points_by_entry.get(row['entry_id'], 0))} pts"
        for _, row in entries.iterrows()
    ]
    ids = entries["entry_id"].tolist()
    current = st.session_state.get("active_entry_id")
    index = ids.index(current) if current in ids else 0

    selected = st.radio("Selecciona cuál quiniela quieres llenar", labels, index=index)
    st.caption("La quiniela seleccionada será la que uses para capturar predicciones.")
    st.session_state["active_entry_id"] = ids[labels.index(selected)]

selected_row = entries.iloc[labels.index(selected)].to_dict()
selected_name = clean_text(selected_row.get("entry_name")) or "Quiniela"
selected_entry_id = clean_text(selected_row.get("entry_id"))
selected_predictions = data[PREDICTIONS]
captured_predictions = 0
if not selected_predictions.empty:
    captured_predictions = int(
        selected_predictions[selected_predictions["entry_id"] == selected_entry_id]["match_id"].nunique()
    )
total_matches = len(data[MATCHES])

st.markdown(
    (
        '<section class="qm-status-panel">'
        '<div class="qm-status-panel-item">'
        '<span class="qm-status-panel-icon">✅</span>'
        '<span>'
        f'<strong>{escape(selected_name)}</strong>'
        '<small>Estás llenando</small>'
        '</span>'
        '</div>'
        '<div class="qm-status-panel-item">'
        '<span class="qm-status-panel-icon">🎟️</span>'
        '<span>'
        f'<strong>{total_entries}</strong>'
        '<small>Entradas disponibles</small>'
        '</span>'
        '</div>'
        '<div class="qm-status-panel-item">'
        '<span class="qm-status-panel-icon">⚽</span>'
        '<span>'
        f'<strong>{captured_predictions}/{total_matches}</strong>'
        '<small>Predicciones capturadas</small>'
        '</span>'
        '</div>'
        '</section>'
    ),
    unsafe_allow_html=True,
)

section_header(
    f"Captura predicciones de {selected_name}",
    "Llena tus marcadores antes del cierre de predicciones.",
)

render_predictions_capture(
    entry=selected_row,
    data=data,
    config=config,
    repo=repo,
    title="Empieza a jugar",
    subtitle="Captura tus marcadores para la fase de grupos.",
    eyebrow="Predicciones",
    show_hero=False,
    compact_summary=True,
)
