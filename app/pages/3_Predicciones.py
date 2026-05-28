"""Predictions page."""

from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import pandas as pd
import streamlit as st

from components.layout import active_entry, configure_page, render_sidebar, require_login
from components.ui import empty_state, info_card, metric_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import AWAY_WIN, DRAW, HOME_WIN, MATCHES, PREDICTIONS
from utils.data import as_int, clean_text
from utils.scoring import result_from_score
from utils.time import is_global_prediction_lock_active, is_match_locked, parse_match_datetime


MONTHS_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _clean_html(markup: str) -> str:
    """Remove indentation so Markdown does not render HTML as a code block."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).strip().splitlines()
        if line.strip()
    )


def _html(markup: str) -> None:
    """Render HTML safely."""
    st.markdown(_clean_html(markup), unsafe_allow_html=True)


def _date_label(value: Any) -> str:
    """Return a Spanish date label."""
    parsed = parse_match_datetime(value)
    if parsed is None:
        return "Fecha por definir"
    return f"{parsed.day} de {MONTHS_ES[parsed.month]}"


def _time_label(value: Any) -> str:
    """Return HH:MM time label."""
    parsed = parse_match_datetime(value)
    if parsed is None:
        return "--:--"
    return parsed.strftime("%H:%M")


def _prediction_for_match(entry_predictions: pd.DataFrame, match_id: str) -> dict[str, Any]:
    """Return the current prediction for a match."""
    if entry_predictions.empty:
        return {}

    existing = entry_predictions[entry_predictions["match_id"] == match_id]

    if existing.empty:
        return {}

    return existing.iloc[0].to_dict()


def _result_label(home_team: str, away_team: str, home_goals: int, away_goals: int) -> str:
    """Return the human readable result label from a score."""
    result = result_from_score(home_goals, away_goals)

    if result == HOME_WIN:
        return f"Gana {home_team}"

    if result == AWAY_WIN:
        return f"Gana {away_team}"

    return "Empate"


def _result_options(home_team: str, away_team: str) -> dict[str, str]:
    """Return result options for the match."""
    return {
        HOME_WIN: f"Gana {home_team}",
        DRAW: "Empate",
        AWAY_WIN: f"Gana {away_team}",
    }


def _status_label(current_prediction: dict[str, Any], locked: bool) -> str:
    """Return match prediction status label."""
    if locked:
        return "Bloqueado"

    if current_prediction:
        return "Guardada"

    return "Abierto"


def _status_accent(current_prediction: dict[str, Any], locked: bool) -> str:
    """Return CSS accent for match prediction status."""
    if locked:
        return "red"

    if current_prediction:
        return "green"

    return "gold"


def _render_date_header(date_label: str, matches_count: int) -> None:
    """Render a polished date header."""
    _html(
        f"""
        <div class="qm-date-header">
            <div>
                <div class="qm-date-title">{escape(date_label)}</div>
                <div class="qm-date-subtitle">{matches_count} partidos programados</div>
            </div>
            <span class="qm-status-pill qm-accent-navy">Fase de grupos</span>
        </div>
        """
    )


def _render_lock_notice(is_locked: bool, lock_at: str) -> None:
    """Render global lock/edit notice."""
    if is_locked:
        info_card(
            "Predicciones cerradas",
            "La edición de predicciones ya está bloqueada para esta fase.",
            icon="🔒",
            accent="red",
        )
    else:
        info_card(
            "Predicciones abiertas",
            f"Puedes editar tus predicciones hasta {lock_at}. Después quedarán bloqueadas.",
            icon="📝",
            accent="navy",
        )


def _render_match_intro(
    match_id: str,
    group_label: str,
    time_label: str,
    status_label: str,
    status_accent: str,
    home_team: str,
    away_team: str,
) -> None:
    """Render the static match card intro."""
    _html(
    f"""
    <div class="qm-match-card qm-accent-{escape(status_accent)}">
        <div class="qm-match-top">
            <div>
                <div class="qm-match-group">Grupo {escape(group_label)}</div>
            </div>
            <div class="qm-match-time">{escape(time_label)}</div>
        </div>
        <div class="qm-match-status-row">
            <span class="qm-status-pill qm-accent-{escape(status_accent)}">{escape(status_label)}</span>
        </div>
        <div class="qm-match-teams">
            <div class="qm-team-name">{escape(home_team)}</div>
            <div class="qm-vs-chip">VS</div>
            <div class="qm-team-name qm-team-right">{escape(away_team)}</div>
        </div>
    </div>
    """
)


def _render_match_card(
    match: dict[str, Any],
    current_prediction: dict[str, Any],
    entry_id: str,
    locked: bool,
    repo: Any,
) -> None:
    """Render one match prediction card."""
    match_id = clean_text(match.get("match_id"))
    home_team = clean_text(match.get("home_team")) or "Local"
    away_team = clean_text(match.get("away_team")) or "Visitante"
    group_label = clean_text(match.get("group")) or "-"
    time_label = _time_label(match.get("match_date"))
    status_label = _status_label(current_prediction, locked)
    status_accent = _status_accent(current_prediction, locked)

    _render_match_intro(
        match_id=match_id,
        group_label=group_label,
        time_label=time_label,
        status_label=status_label,
        status_accent=status_accent,
        home_team=home_team,
        away_team=away_team,
    )

    default_home = as_int(current_prediction.get("pred_home_goals"), 0)
    default_away = as_int(current_prediction.get("pred_away_goals"), 0)

    with st.form(f"prediction_{match_id}", border=True):
        score_left, score_middle, score_right = st.columns([1, 0.28, 1])

        home_goals = score_left.number_input(
            f"Goles de {home_team}",
            min_value=0,
            max_value=20,
            value=default_home,
            disabled=locked,
            key=f"home_{match_id}",
            label_visibility="collapsed",
        )

        score_middle.markdown(
            "<div class='qm-score-vs'>VS</div>",
            unsafe_allow_html=True,
        )

        away_goals = score_right.number_input(
            f"Goles de {away_team}",
            min_value=0,
            max_value=20,
            value=default_away,
            disabled=locked,
            key=f"away_{match_id}",
            label_visibility="collapsed",
        )

        calculated_result = result_from_score(home_goals, away_goals)
        options = _result_options(home_team, away_team)
        option_keys = list(options.keys())
        saved_result = clean_text(current_prediction.get("selected_result"))
        selected_index = (
            option_keys.index(saved_result)
            if saved_result in option_keys
            else option_keys.index(calculated_result)
        )

        selected_result = st.selectbox(
            "Quién gana",
            option_keys,
            index=selected_index,
            format_func=lambda key: options[key],
            disabled=locked,
            key=f"winner_{match_id}",
        )

        calculated_label = _result_label(home_team, away_team, home_goals, away_goals)

        st.markdown(
            f"""
            <div class="qm-calculated-result">
                Según el marcador: <strong>{escape(calculated_label)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        button_label = "Editar predicción" if current_prediction else "Guardar predicción"

        submitted = st.form_submit_button(
            button_label,
            disabled=locked,
            use_container_width=True,
        )

    if submitted:
        if selected_result != calculated_result:
            st.error("El ganador seleccionado debe coincidir con el marcador capturado.")
        else:
            try:
                repo.upsert_prediction(
                    entry_id=entry_id,
                    match_id=match_id,
                    selected_result=selected_result,
                    pred_home_goals=home_goals,
                    pred_away_goals=away_goals,
                )
                st.success("Predicción guardada.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


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

matches = data[MATCHES]

if matches.empty:
    page_hero(
        "Predicciones",
        "Aún no hay calendario cargado para capturar marcadores.",
        eyebrow="Captura de resultados",
        pills=[f"Quiniela activa: {clean_text(entry.get('entry_name'))}"],
    )
    empty_state(
        "Aún no hay partidos cargados",
        "Cuando cargues el calendario, aquí podrás capturar tus predicciones.",
        icon="📅",
    )
    st.stop()

predictions = data[PREDICTIONS]

entry_predictions = pd.DataFrame()
if not predictions.empty:
    entry_predictions = predictions[predictions["entry_id"] == entry["entry_id"]]

matches = matches.copy()
matches["parsed_date"] = matches["match_date"].apply(parse_match_datetime)
matches["date_label"] = matches["match_date"].apply(_date_label)
matches["group_label"] = matches["group"].apply(lambda value: clean_text(value) or "-")
matches = matches.sort_values("parsed_date", na_position="last")

captured = 0 if entry_predictions.empty else int(entry_predictions["match_id"].nunique())
total_matches = len(matches)
pending = max(total_matches - captured, 0)
entry_points = (
    0
    if entry_predictions.empty or "points" not in entry_predictions.columns
    else int(entry_predictions["points"].apply(lambda value: as_int(value, 0)).sum())
)
lock_at = clean_text(config.get("predictions_lock_at")) or "2026-06-10 23:59"
global_locked = is_global_prediction_lock_active(config)

page_hero(
    "Predicciones",
    "Captura tus marcadores para la fase de grupos.",
    eyebrow="Captura de resultados",
    pills=[
        f"Quiniela activa: {clean_text(entry.get('entry_name'))}",
        f"{captured} capturadas",
        f"{pending} pendientes",
        f"{total_matches} partidos",
    ],
)

section_header("Resumen de captura", "Avance actual de tu quiniela seleccionada.")

summary_cols = st.columns(4)

with summary_cols[0]:
    metric_card("Capturadas", str(captured), "Predicciones guardadas", "green")

with summary_cols[1]:
    metric_card("Pendientes", str(pending), "Por capturar", "gold")

with summary_cols[2]:
    metric_card("Total partidos", str(total_matches), "Fase de grupos", "navy")

with summary_cols[3]:
    metric_card("Puntos", str(entry_points), "Quiniela actual", "green")

_render_lock_notice(global_locked, lock_at)

section_header("Filtrar partidos", "Encuentra rápido los partidos por fecha, grupo o estado.")

filter_col1, filter_col2, filter_col3 = st.columns(3)

date_options = ["Todas"] + list(dict.fromkeys(matches["date_label"].tolist()))
group_options = ["Todos"] + sorted(matches["group_label"].dropna().unique().tolist())

date_filter = filter_col1.selectbox("Fecha", date_options)
group_filter = filter_col2.selectbox("Grupo", group_options)
status_filter = filter_col3.selectbox(
    "Estado",
    ["Todos", "Pendientes", "Guardadas", "Bloqueadas"],
)

filtered_matches = matches.copy()

if date_filter != "Todas":
    filtered_matches = filtered_matches[filtered_matches["date_label"] == date_filter]

if group_filter != "Todos":
    filtered_matches = filtered_matches[filtered_matches["group_label"] == group_filter]

visible_rows: list[tuple[int, pd.Series, dict[str, Any], bool]] = []

for index, match in filtered_matches.iterrows():
    match_id = clean_text(match.get("match_id"))
    current_prediction = _prediction_for_match(entry_predictions, match_id)
    locked = is_match_locked(match.to_dict(), config)

    if status_filter == "Pendientes" and current_prediction:
        continue

    if status_filter == "Guardadas" and not current_prediction:
        continue

    if status_filter == "Bloqueadas" and not locked:
        continue

    visible_rows.append((index, match, current_prediction, locked))

if not visible_rows:
    empty_state(
        "No hay partidos para estos filtros",
        "Cambia la fecha, el grupo o el estado para ver más partidos.",
        icon="🔎",
    )
    st.stop()

for date_label in dict.fromkeys(row[1]["date_label"] for row in visible_rows):
    day_rows = [row for row in visible_rows if row[1]["date_label"] == date_label]

    _render_date_header(date_label, len(day_rows))

    for start in range(0, len(day_rows), 2):
        columns = st.columns(2)

        for column, (_, match, current_prediction, locked) in zip(
            columns,
            day_rows[start : start + 2],
        ):
            with column:
                _render_match_card(
                    match.to_dict(),
                    current_prediction,
                    entry["entry_id"],
                    locked or global_locked,
                    repo,
                )