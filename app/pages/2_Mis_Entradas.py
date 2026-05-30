"""User entries page."""

from __future__ import annotations

from html import escape
from textwrap import dedent

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login, user_entries
from components.ui import empty_state, info_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import MATCHES, PREDICTIONS, RESULTS, USERS
from utils.data import as_int, clean_text
from utils.predictions import build_entry_prediction_summary
from utils.rankings import build_rankings


def _clean_html(markup: str) -> str:
    """Remove indentation so Markdown does not render HTML as a code block."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).strip().splitlines()
        if line.strip()
    )


def _render_entry_review_list(
    entries,
    points_by_entry: dict[str, object],
    captured_by_entry: dict[str, object],
    total_matches: int,
    selected_entry_id: str,
    active_entry_id: str | None,
) -> None:
    """Render a compact visual list for reviewing entries."""
    rows = []

    for _, entry in entries.iterrows():
        entry_id = clean_text(entry.get("entry_id"))
        entry_name = clean_text(entry.get("entry_name")) or "Quiniela"
        created_at = clean_text(entry.get("created_at")) or "-"
        points = int(points_by_entry.get(entry_id, 0))
        captured = int(captured_by_entry.get(entry_id, 0))
        is_selected = entry_id == selected_entry_id
        is_active = entry_id == active_entry_id
        selected_class = " qm-entry-review-row-selected" if is_selected else ""
        selected_label = '<span class="qm-entry-review-selected">En revisión</span>' if is_selected else ""
        status_label = "Activa" if is_active else "Disponible"
        status_accent = "green" if is_active else "navy"

        rows.append(
            f"""
            <div class="qm-entry-review-row{selected_class}">
                <div class="qm-entry-review-main">
                    <div class="qm-entry-review-name">{escape(entry_name)}</div>
                    <div class="qm-entry-review-date">Creada: {escape(created_at)}</div>
                </div>
                <div class="qm-entry-review-metric">
                    <strong>{points}</strong>
                    <small>pts</small>
                </div>
                <div class="qm-entry-review-metric">
                    <strong>{captured}/{total_matches}</strong>
                    <small>predicciones</small>
                </div>
                <div class="qm-entry-review-status">
                    <span class="qm-status-pill qm-accent-{status_accent}">{escape(status_label)}</span>
                    {selected_label}
                </div>
            </div>
            """
        )

    st.markdown(
        _clean_html(
            f"""
            <section class="qm-entry-review-list">
                {''.join(rows)}
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


configure_page("Mis quinielas")
user = require_login()
repo = get_repository_or_stop()
data = repo.load_data()
render_sidebar(data)

if st.session_state.pop("entry_delete_success", False):
    st.success("Quiniela eliminada correctamente.")

entries = user_entries(data, user["user_id"])
rankings = build_rankings(entries, data[USERS], data[PREDICTIONS], data[RESULTS])

points_by_entry = {}
captured_by_entry = {}
if not rankings.empty:
    points_by_entry = rankings.set_index("entry_id")["total_points"].to_dict()
    captured_by_entry = rankings.set_index("entry_id")["predictions_count"].to_dict()

total_entries = len(entries)
total_points = int(sum(as_int(value, 0) for value in points_by_entry.values()))
total_matches = len(data[MATCHES])
total_captured = int(sum(as_int(value, 0) for value in captured_by_entry.values()))

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
    "Consulta tus entradas, revisa tus puntos y el avance de tus predicciones.",
    eyebrow="Resumen personal",
    pills=[
        f"{clean_text(user.get('nickname')) or 'Usuario'}",
        f"{total_entries} quinielas",
        f"{total_points} pts totales",
    ],
)


section_header(
    "Resumen de tus entradas",
    "Vista rápida de tus quinielas, puntos acumulados y avance de captura.",
)

st.markdown(
    _clean_html(
        f"""
        <section class="qm-status-panel qm-status-panel-four">
            <div class="qm-status-panel-item">
                <span class="qm-status-panel-icon">🎟️</span>
                <span>
                    <strong>{total_entries}</strong>
                    <small>Total de quinielas</small>
                </span>
            </div>
            <div class="qm-status-panel-item">
                <span class="qm-status-panel-icon">✅</span>
                <span>
                    <strong>{escape(active_entry_name)}</strong>
                    <small>Quiniela activa</small>
                </span>
            </div>
            <div class="qm-status-panel-item qm-status-panel-money">
                <span class="qm-status-panel-icon">🏆</span>
                <span>
                    <strong>{total_points} pts</strong>
                    <small>Puntos totales</small>
                </span>
            </div>
            <div class="qm-status-panel-item">
                <span class="qm-status-panel-icon">⚽</span>
                <span>
                    <strong>{total_captured}</strong>
                    <small>Predicciones capturadas</small>
                </span>
            </div>
        </section>
        """
    ),
    unsafe_allow_html=True,
)


section_header("Tus quinielas", "Elige cuál quieres revisar en detalle.")

if entries.empty:
    empty_state(
        "Aún no tienes quinielas",
        "Ve a Empieza a jugar para crear tu primera quiniela y capturar predicciones.",
        icon="🎟️",
    )
    st.page_link("pages/0_Empieza_A_Jugar.py", label="Crear quiniela en Empieza A Jugar")
else:
    ids = entries["entry_id"].tolist()
    review_entry_id = st.session_state.get("review_entry_id")

    if review_entry_id not in ids:
        review_entry_id = current_entry_id if current_entry_id in ids else ids[0]

    index = ids.index(review_entry_id) if review_entry_id in ids else 0

    def _entry_select_label(entry_id: str) -> str:
        """Return the review selector label for one entry."""
        row = entries[entries["entry_id"] == entry_id].iloc[0]
        entry_name = clean_text(row.get("entry_name")) or "Quiniela"
        points = int(points_by_entry.get(entry_id, 0))
        captured = int(captured_by_entry.get(entry_id, 0))
        active_suffix = " · activa" if entry_id == current_entry_id else ""
        return f"{entry_name} · {points} pts · {captured}/{total_matches} predicciones{active_suffix}"

    selected_entry_id = st.selectbox(
        "Selecciona la quiniela que quieres revisar",
        ids,
        index=index,
        format_func=_entry_select_label,
    )
    st.session_state["review_entry_id"] = selected_entry_id

    selected_row = entries[entries["entry_id"] == selected_entry_id].iloc[0]
    selected_name = clean_text(selected_row.get("entry_name")) or "Quiniela"
    selected_points = int(points_by_entry.get(selected_entry_id, 0))
    selected_captured = int(captured_by_entry.get(selected_entry_id, 0))
    selected_status = "Activa" if selected_entry_id == current_entry_id else "Disponible"

    _render_entry_review_list(
        entries,
        points_by_entry,
        captured_by_entry,
        total_matches,
        selected_entry_id,
        current_entry_id,
    )

    section_header("Eliminar quiniela", "Esta acción borra la quiniela seleccionada y sus predicciones.")
    info_card(
        selected_name,
        (
            f"{selected_captured}/{total_matches} predicciones capturadas · "
            f"{selected_points} pts · {selected_status}"
        ),
        icon="🗑️",
        accent="red",
    )

    confirm_delete = st.checkbox(
        "Confirmo que quiero eliminar esta quiniela y sus predicciones.",
        key=f"confirm_delete_user_entry_{selected_entry_id}",
    )

    if st.button(
        "Eliminar quiniela",
        use_container_width=True,
        disabled=not confirm_delete,
        type="secondary",
    ):
        try:
            selected_owner_id = clean_text(selected_row.get("user_id"))

            if selected_owner_id != clean_text(user.get("user_id")):
                st.error("No puedes eliminar una quiniela de otro usuario.")
                st.stop()

            deleted = repo.delete_entry(selected_entry_id)

            if not deleted:
                st.error("No se pudo eliminar la quiniela seleccionada.")
                st.stop()

            remaining_entries = entries[entries["entry_id"] != selected_entry_id]
            remaining_ids = remaining_entries["entry_id"].tolist()

            if current_entry_id == selected_entry_id:
                if remaining_ids:
                    st.session_state["active_entry_id"] = remaining_ids[0]
                else:
                    st.session_state.pop("active_entry_id", None)

            if remaining_ids:
                next_review_id = st.session_state.get("active_entry_id")
                if next_review_id not in remaining_ids:
                    next_review_id = remaining_ids[0]
                st.session_state["review_entry_id"] = next_review_id
            else:
                st.session_state.pop("review_entry_id", None)

            st.session_state["entry_delete_success"] = True
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    section_header(
        f"Predicciones de {selected_name}",
        "Resumen de captura para la quiniela seleccionada.",
    )

    summary = build_entry_prediction_summary(
        data[MATCHES],
        data[PREDICTIONS],
        selected_entry_id,
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

        st.markdown(
            _clean_html(
                f"""
                <section class="qm-status-panel qm-status-panel-four">
                    <div class="qm-status-panel-item">
                        <span class="qm-status-panel-icon">⚽</span>
                        <span>
                            <strong>{total_matches}</strong>
                            <small>Total partidos</small>
                        </span>
                    </div>
                    <div class="qm-status-panel-item">
                        <span class="qm-status-panel-icon">✅</span>
                        <span>
                            <strong>{captured_predictions}</strong>
                            <small>Predicciones capturadas</small>
                        </span>
                    </div>
                    <div class="qm-status-panel-item">
                        <span class="qm-status-panel-icon">⏳</span>
                        <span>
                            <strong>{pending_predictions}</strong>
                            <small>Pendientes</small>
                        </span>
                    </div>
                    <div class="qm-status-panel-item qm-status-panel-money">
                        <span class="qm-status-panel-icon">🏆</span>
                        <span>
                            <strong>{selected_points} pts</strong>
                            <small>Puntos de esta quiniela</small>
                        </span>
                    </div>
                </section>
                """
            ),
            unsafe_allow_html=True,
        )

        if captured_predictions == 0:
            info_card(
                "Sin predicciones capturadas",
                "Todavía no has guardado marcadores para esta quiniela.",
                icon="📝",
                accent="gold",
            )

        display = summary.copy()
        display["Partido"] = display.apply(
            lambda row: (
                f"{clean_text(row.get('home_team')) or '-'}"
                f" vs {clean_text(row.get('away_team')) or '-'}"
            ),
            axis=1,
        )
        display = display.rename(
            columns={
                "match_date": "Fecha",
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
