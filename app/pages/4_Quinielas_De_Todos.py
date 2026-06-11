"""Read-only public entries page."""

from __future__ import annotations

from html import escape
from textwrap import dedent

import pandas as pd
import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from components.ui import empty_state, info_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, MATCHES, PREDICTIONS, RESULTS, USERS
from utils.data import as_bool, as_int, clean_text
from utils.predictions import build_entry_prediction_summary
from utils.rankings import build_rankings
from utils.time import is_global_prediction_lock_active


def _clean_html(markup: str) -> str:
    """Remove indentation so Markdown does not render HTML as a code block."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).strip().splitlines()
        if line.strip()
    )


def _short_date(value: object) -> str:
    """Render a compact Spanish date label."""
    parsed = pd.to_datetime(clean_text(value), errors="coerce")
    if pd.isna(parsed):
        return "-"

    months = {
        1: "Ene",
        2: "Feb",
        3: "Mar",
        4: "Abr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dic",
    }
    return f"{parsed.day} {months.get(parsed.month, '')}".strip()


def _render_entry_summary(
    entry_name: str,
    nickname: str,
    total_points: int,
    captured_predictions: int,
    total_matches: int,
    paid: bool,
) -> None:
    """Render a compact read-only summary for the selected entry."""
    payment_label = "✅ Pagada" if paid else "⏳ Pendiente"

    st.markdown(
        _clean_html(
            f"""
            <section class="qm-status-panel">
                <div class="qm-status-panel-item">
                    <span class="qm-status-panel-icon">🎟️</span>
                    <span>
                        <strong>{escape(entry_name)}</strong>
                        <small>Quiniela</small>
                    </span>
                </div>
                <div class="qm-status-panel-item">
                    <span class="qm-status-panel-icon">👤</span>
                    <span>
                        <strong>{escape(nickname)}</strong>
                        <small>Jugador</small>
                    </span>
                </div>
                <div class="qm-status-panel-item qm-status-panel-money">
                    <span class="qm-status-panel-icon">🏆</span>
                    <span>
                        <strong>{total_points} pts</strong>
                        <small>Puntos actuales</small>
                    </span>
                </div>
                <div class="qm-status-panel-item">
                    <span class="qm-status-panel-icon">⚽</span>
                    <span>
                        <strong>{captured_predictions}/{total_matches}</strong>
                        <small>Predicciones capturadas</small>
                    </span>
                </div>
                <div class="qm-status-panel-item">
                    <span class="qm-status-panel-icon">💵</span>
                    <span>
                        <strong>{escape(payment_label)}</strong>
                        <small>Estado de pago</small>
                    </span>
                </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


configure_page("Quinielas de todos")
require_login()
repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

page_hero(
    "Quinielas de todos",
    "Consulta las predicciones de todos los participantes cuando la captura esté cerrada.",
    eyebrow="Vista social",
    pills=["Solo lectura", "Todas las quinielas", "Después del cierre"],
)

if not is_global_prediction_lock_active(config):
    info_card(
        "Disponible después del cierre",
        "Para evitar copias, las quinielas de todos se podrán consultar cuando cierre la captura.",
        icon="🔒",
        accent="gold",
    )
    st.stop()

entries = data[ENTRIES]
matches = data[MATCHES]
predictions = data[PREDICTIONS]
rankings = build_rankings(entries, data[USERS], predictions, data[RESULTS])
total_matches = len(matches)

section_header(
    "Todas las quinielas",
    "Elige una entrada para revisar sus marcadores en modo solo lectura.",
)

if rankings.empty:
    empty_state(
        "Aún no hay quinielas registradas.",
        "Cuando existan quinielas activas, aquí podrás consultarlas después del cierre.",
        icon="🎟️",
    )
    st.stop()


def _selector_label(entry_id: str) -> str:
    """Return the selectbox label for one active entry."""
    row = rankings[rankings["entry_id"] == entry_id].iloc[0]
    entry_name = clean_text(row.get("entry_name")) or "Quiniela"
    nickname = clean_text(row.get("nickname")) or "Sin apodo"
    captured = as_int(row.get("predictions_count"), 0)
    return f"{entry_name} · {nickname} · {captured}/{total_matches} predicciones"


entry_ids = rankings["entry_id"].tolist()
selected_entry_id = st.selectbox(
    "Selecciona una quiniela",
    entry_ids,
    format_func=_selector_label,
)

selected_ranking = rankings[rankings["entry_id"] == selected_entry_id].iloc[0]
selected_entry_name = clean_text(selected_ranking.get("entry_name")) or "Quiniela"
selected_nickname = clean_text(selected_ranking.get("nickname")) or "Sin apodo"
selected_points = as_int(selected_ranking.get("total_points"), 0)
selected_captured = as_int(selected_ranking.get("predictions_count"), 0)
selected_paid = as_bool(selected_ranking.get("paid"))

_render_entry_summary(
    selected_entry_name,
    selected_nickname,
    selected_points,
    selected_captured,
    total_matches,
    selected_paid,
)

section_header(
    f"Predicciones de {selected_entry_name}",
    "Marcadores capturados por esta quiniela.",
)

if selected_captured == 0:
    empty_state(
        "Esta quiniela aún no tiene predicciones capturadas.",
        "Cuando existan predicciones guardadas, aquí aparecerá el detalle.",
        icon="📝",
    )
    st.stop()

summary = build_entry_prediction_summary(matches, predictions, selected_entry_id)

if summary.empty:
    empty_state(
        "Aún no hay partidos cargados.",
        "Cuando exista calendario, aquí aparecerán las predicciones.",
        icon="📅",
    )
    st.stop()

display = summary.copy()
display["Fecha"] = display["match_date"].apply(_short_date)
display["Partido"] = display.apply(
    lambda row: (
        f"{clean_text(row.get('home_team')) or '-'}"
        f" vs {clean_text(row.get('away_team')) or '-'}"
    ),
    axis=1,
)
display = display.rename(
    columns={
        "selected_result_label": "Quién gana",
        "prediction": "Marcador capturado",
        "capture_status": "Estado",
        "points": "Puntos",
    }
)

st.dataframe(
    display[
        [
            "Fecha",
            "Partido",
            "Marcador capturado",
            "Quién gana",
            "Estado",
            "Puntos",
        ]
    ],
    hide_index=True,
    use_container_width=True,
)
