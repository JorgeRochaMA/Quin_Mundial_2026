"""Stats page."""

from __future__ import annotations

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, MATCHES, PREDICTIONS, RESULTS, USERS
from utils.stats import build_pool_stats


configure_page("Estadísticas")
require_login()
repo = get_repository_or_stop()
data = repo.load_data()
render_sidebar(data)

st.title("Estadísticas")

stats = build_pool_stats(
    data[ENTRIES],
    data[USERS],
    data[PREDICTIONS],
    data[RESULTS],
    data[MATCHES],
)

most_exact = stats["most_exact"]
best_accuracy = stats["best_accuracy"]
riskiest = stats["riskiest"]
popular_score = stats["popular_score"]

st.caption("Esta sección sirve para leer tendencias de la quiniela cuando ya hay resultados oficiales.")

col1, col2, col3, col4 = st.columns(4)
if most_exact:
    col1.metric("Más exactos", most_exact["entry_name"], int(most_exact["exact_scores"]))
else:
    col1.metric("Más exactos", "Sin datos")

if best_accuracy:
    col2.metric("Mejor efectividad", best_accuracy["entry_name"], f"{best_accuracy['accuracy']:.0%}")
else:
    col2.metric("Mejor efectividad", "Sin datos")

if riskiest:
    col3.metric("Más arriesgada", riskiest["entry_name"], f"{riskiest['avg_predicted_goals']:.1f} goles")
else:
    col3.metric("Más arriesgada", "Sin datos")

if popular_score:
    col4.metric("Marcador más repetido", popular_score["scoreline"], f"{int(popular_score['predictions'])} veces")
else:
    col4.metric("Marcador más repetido", "Sin datos")

st.caption("La quiniela más arriesgada se calcula por promedio de goles pronosticados.")

group_summary = stats["group_summary"]
st.subheader("Rendimiento por grupo")
if group_summary.empty:
    st.info("Aún no hay resultados suficientes para calcular estadísticas por grupo.")
else:
    display = group_summary.rename(
        columns={
            "group": "Grupo",
            "avg_points": "Puntos promedio",
            "predictions": "Predicciones",
            "exact_scores": "Exactos",
        }
    )
    st.dataframe(display, hide_index=True, use_container_width=True)
