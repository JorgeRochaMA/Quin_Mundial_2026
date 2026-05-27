"""User entries page."""

from __future__ import annotations

from html import escape
from textwrap import dedent

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login, user_entries
from components.ui import empty_state, info_card, metric_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import MATCHES, PREDICTIONS, RESULTS, USERS
from utils.data import as_bool, as_int, clean_text
from utils.predictions import build_entry_prediction_summary
from utils.rankings import build_rankings


def _clean_html(markup: str) -> str:
    """Remove indentation so Markdown does not render HTML as a code block."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).strip().splitlines()
        if line.strip()
    )


def _entry_card(
    entry: dict[str, object],
    points: int,
    is_selected: bool,
) -> None:
    """Render one entry management card."""
    selected_class = "qm-entry-selected" if is_selected else ""
    selected_label = "Seleccionada" if is_selected else "Disponible"
    selected_accent = "green" if is_selected else "navy"
    paid_label = "Pagada" if as_bool(entry.get("paid")) else "Pago pendiente"
    active_label = "Activa" if as_bool(entry.get("active")) else "Inactiva"

    markup = f"""
    <div class="qm-entry-card {selected_class}">
        <div class="qm-entry-card-top">
            <div>
                <div class="qm-entry-name">{escape(clean_text(entry.get("entry_name")) or "Quiniela")}</div>
                <div class="qm-entry-date">Creada: {escape(clean_text(entry.get("created_at")) or "-")}</div>
            </div>
            <span class="qm-status-pill qm-accent-{selected_accent}">{escape(selected_label)}</span>
        </div>
        <div class="qm-entry-points">{points} pts</div>
        <div class="qm-entry-meta">
            <span>{escape(paid_label)}</span>
            <span>{escape(active_label)}</span>
        </div>
    </div>
    """

    st.markdown(_clean_html(markup), unsafe_allow_html=True)


configure_page("Mis quinielas")
user = require_login()
repo = get_repository_or_stop()
data = repo.load_data()
render_sidebar(data)

entries = user_entries(data, user["user_id"])
rankings = build_rankings(entries, data[USERS], data[PREDICTIONS], data[RESULTS])

points_by_entry = {}
if not rankings.empty:
    points_by_entry = rankings.set_index("entry_id")["total_points"].to_dict()

total_entries = len(entries)
total_points = int(sum(as_int(value, 0) for value in points_by_entry.values()))

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
    "Mis quinielas",
    "Administra tus entradas, revisa tus puntos y elige tu quiniela activa.",
    eyebrow="Gestión personal",
    pills=[
        f"{clean_text(user.get('nickname')) or 'Usuario'}",
        f"{total_entries} quinielas",
        f"{total_points} pts totales",
    ],
)


section_header("Tu contexto", "Resumen rápido de tus entradas en esta quiniela.")

context_cols = st.columns(4)

with context_cols[0]:
    metric_card("Nickname", clean_text(user.get("nickname")) or "-", "Usuario actual", "green")

with context_cols[1]:
    metric_card("Total quinielas", str(total_entries), "Entradas activas", "gold")

with context_cols[2]:
    metric_card("Quiniela activa", active_entry_name, "Seleccionada", "navy")

with context_cols[3]:
    metric_card("Puntos totales", str(total_points), "Suma de tus quinielas", "green")


section_header(
    "Crear otra quiniela",
    "Cada quiniela participa de forma independiente en la tabla general.",
)

info_card(
    "Nueva entrada",
    "Al crearla se agrega a tus quinielas y queda seleccionada como activa.",
    icon="🎟️",
    accent="gold",
)

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


section_header("Tus quinielas", "Elige cuál usarás para capturar o revisar predicciones.")

if entries.empty:
    empty_state(
        "Aún no tienes quinielas",
        "Crea tu primera quiniela para empezar a capturar predicciones.",
        icon="🎟️",
    )
else:
    labels = [
        f"{row['entry_name']} · {int(points_by_entry.get(row['entry_id'], 0))} pts"
        for _, row in entries.iterrows()
    ]

    ids = entries["entry_id"].tolist()
    current = st.session_state.get("active_entry_id")
    index = ids.index(current) if current in ids else 0

    selected = st.radio("Selecciona tu quiniela activa", labels, index=index)
    st.session_state["active_entry_id"] = ids[labels.index(selected)]

    selected_row = entries.iloc[labels.index(selected)]
    selected_name = clean_text(selected_row.get("entry_name")) or "Quiniela"

    for start in range(0, len(entries), 3):
        columns = st.columns(3)

        for column, (_, entry_row) in zip(columns, entries.iloc[start : start + 3].iterrows()):
            entry_id = entry_row.get("entry_id")

            with column:
                _entry_card(
                    entry_row.to_dict(),
                    int(points_by_entry.get(entry_id, 0)),
                    entry_id == st.session_state["active_entry_id"],
                )

    display = entries.copy()
    display["Puntos"] = display["entry_id"].map(points_by_entry).fillna(0).astype(int)
    display["Pagada"] = display["paid"].apply(lambda value: "Sí" if as_bool(value) else "No")
    display["Activa"] = display["active"].apply(lambda value: "Sí" if as_bool(value) else "No")

    display = display.rename(
        columns={
            "entry_name": "Quiniela",
            "created_at": "Creada",
        }
    )

    st.dataframe(
        display[["Quiniela", "Puntos", "Creada", "Pagada", "Activa"]],
        hide_index=True,
        use_container_width=True,
    )

    section_header(
        f"Predicciones de {selected_name}",
        "Resumen de captura para la quiniela seleccionada.",
    )

    summary = build_entry_prediction_summary(
        data[MATCHES],
        data[PREDICTIONS],
        st.session_state["active_entry_id"],
    )

    if summary.empty:
        empty_state(
            "Aún no hay partidos cargados",
            "Cuando se cargue el calendario, aquí verás el avance de tus predicciones.",
            icon="📅",
        )
    else:
        total_matches = len(summary)
        captured_predictions = int((summary["capture_status"] == "Guardada").sum())
        pending_predictions = max(total_matches - captured_predictions, 0)
        selected_points = int(summary["points"].apply(lambda value: as_int(value, 0)).sum())

        summary_cols = st.columns(4)

        with summary_cols[0]:
            metric_card("Total partidos", str(total_matches), "Calendario disponible", "navy")

        with summary_cols[1]:
            metric_card("Capturadas", str(captured_predictions), "Predicciones guardadas", "green")

        with summary_cols[2]:
            metric_card("Pendientes", str(pending_predictions), "Por capturar", "red")

        with summary_cols[3]:
            metric_card("Puntos", str(selected_points), "Quiniela seleccionada", "gold")

        if captured_predictions == 0:
            info_card(
                "Sin predicciones capturadas",
                "Todavía no has guardado marcadores para esta quiniela.",
                icon="📝",
                accent="gold",
            )

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
            display[
                [
                    "Fecha",
                    "Grupo",
                    "Local",
                    "Visitante",
                    "Quién gana",
                    "Predicción",
                    "Estado",
                    "Puntos",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )