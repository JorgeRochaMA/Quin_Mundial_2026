"""User entries page."""

from __future__ import annotations

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login, user_entries
from services.runtime import get_repository_or_stop
from utils.constants import MATCHES, PREDICTIONS, RESULTS, USERS
from utils.predictions import build_entry_prediction_summary
from utils.rankings import build_rankings


configure_page("Mis quinielas")
user = require_login()
repo = get_repository_or_stop()
data = repo.load_data()
render_sidebar(data)

st.title("Mis quinielas")

entries = user_entries(data, user["user_id"])
rankings = build_rankings(entries, data[USERS], data[PREDICTIONS], data[RESULTS])
points_by_entry = {}
if not rankings.empty:
    points_by_entry = rankings.set_index("entry_id")["total_points"].to_dict()

st.subheader("Crear otra quiniela")
st.caption("Al crearla se agrega a tus quinielas y queda seleccionada como activa.")
with st.form("create_entry"):
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

st.subheader("Tus quinielas")
if entries.empty:
    st.info("Crea tu primera quiniela para empezar a capturar predicciones.")
else:
    display = entries.copy()
    display["Puntos"] = display["entry_id"].map(points_by_entry).fillna(0).astype(int)
    display = display.rename(
        columns={
            "entry_name": "Quiniela",
            "created_at": "Creada",
        }
    )
    st.dataframe(
        display[["Quiniela", "Puntos", "Creada"]],
        hide_index=True,
        use_container_width=True,
    )

    labels = [
        f"{row['entry_name']} · {int(points_by_entry.get(row['entry_id'], 0))} pts"
        for _, row in entries.iterrows()
    ]
    ids = entries["entry_id"].tolist()
    current = st.session_state.get("active_entry_id")
    index = ids.index(current) if current in ids else 0
    selected = st.radio("Selecciona tu quiniela activa", labels, index=index)
    st.session_state["active_entry_id"] = ids[labels.index(selected)]
    selected_name = entries.iloc[labels.index(selected)]["entry_name"]

    st.subheader(f"Predicciones de {selected_name}")
    summary = build_entry_prediction_summary(
        data[MATCHES],
        data[PREDICTIONS],
        st.session_state["active_entry_id"],
    )
    if summary.empty:
        st.info("Aún no hay partidos cargados para mostrar predicciones.")
    else:
        display = summary.rename(
            columns={
                "match_date": "Fecha",
                "group": "Grupo",
                "home_team": "Local",
                "away_team": "Visitante",
                "selected_result_label": "Quién gana",
                "prediction": "Predicción",
                "capture_status": "Estado",
                "points": "Puntos",
            }
        )
        st.dataframe(
            display[["Fecha", "Grupo", "Local", "Visitante", "Quién gana", "Predicción", "Estado", "Puntos"]],
            hide_index=True,
            use_container_width=True,
        )
