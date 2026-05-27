"""Predictions page."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import active_entry, configure_page, render_sidebar, require_login
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


def _date_label(value: Any) -> str:
    parsed = parse_match_datetime(value)
    if parsed is None:
        return "Fecha por definir"
    return f"{parsed.day} de {MONTHS_ES[parsed.month]}"


def _time_label(value: Any) -> str:
    parsed = parse_match_datetime(value)
    if parsed is None:
        return "--:--"
    return parsed.strftime("%H:%M")


def _prediction_for_match(entry_predictions: pd.DataFrame, match_id: str) -> dict[str, Any]:
    if entry_predictions.empty:
        return {}
    existing = entry_predictions[entry_predictions["match_id"] == match_id]
    if existing.empty:
        return {}
    return existing.iloc[0].to_dict()


def _result_label(home_team: str, away_team: str, home_goals: int, away_goals: int) -> str:
    result = result_from_score(home_goals, away_goals)
    if result == HOME_WIN:
        return f"Gana {home_team}"
    if result == AWAY_WIN:
        return f"Gana {away_team}"
    return "Empate"


def _result_options(home_team: str, away_team: str) -> dict[str, str]:
    return {
        HOME_WIN: f"Gana {home_team}",
        DRAW: "Empate",
        AWAY_WIN: f"Gana {away_team}",
    }


def _render_match_card(
    match: dict[str, Any],
    current_prediction: dict[str, Any],
    entry_id: str,
    locked: bool,
    repo: Any,
) -> None:
    match_id = clean_text(match.get("match_id"))
    home_team = clean_text(match.get("home_team")) or "Local"
    away_team = clean_text(match.get("away_team")) or "Visitante"
    group_label = clean_text(match.get("group")) or "-"
    time_label = _time_label(match.get("match_date"))
    status_label = "Bloqueado" if locked else ("Guardada" if current_prediction else "Abierto")

    with st.container(border=True):
        top_left, top_right = st.columns([1, 0.35])
        top_left.markdown(f"**Grupo {group_label}**")
        top_right.markdown(f"**{time_label}**")
        st.caption(status_label)

        team_left, score_col, team_right = st.columns([1, 1.1, 1])
        team_left.markdown(f"**{home_team}**")
        team_right.markdown(f"**{away_team}**")

        default_home = as_int(current_prediction.get("pred_home_goals"), 0)
        default_away = as_int(current_prediction.get("pred_away_goals"), 0)

        with st.form(f"prediction_{match_id}"):
            score_left, score_middle, score_right = score_col.columns([1, 0.4, 1])
            home_goals = score_left.number_input(
                "Local",
                min_value=0,
                max_value=20,
                value=default_home,
                disabled=locked,
                key=f"home_{match_id}",
                label_visibility="collapsed",
            )
            score_middle.markdown("**VS**")
            away_goals = score_right.number_input(
                "Visitante",
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
            selected_index = option_keys.index(saved_result) if saved_result in option_keys else option_keys.index(calculated_result)
            selected_result = st.selectbox(
                "Quién gana",
                option_keys,
                index=selected_index,
                format_func=lambda key: options[key],
                disabled=locked,
                key=f"winner_{match_id}",
            )
            st.caption(f"Según el marcador: {_result_label(home_team, away_team, home_goals, away_goals)}")
            button_label = "Editar" if current_prediction else "Guardar"
            submitted = st.form_submit_button(button_label, disabled=locked, use_container_width=True)

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
st.title("Predicciones")

if not entry:
    st.info("Primero crea o selecciona una quiniela en la sección Mis quinielas.")
    st.stop()

matches = data[MATCHES]
if matches.empty:
    st.info("Aún no hay partidos cargados.")
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
lock_at = clean_text(config.get("predictions_lock_at")) or "2026-06-10 23:59"

st.caption(f"Quiniela activa: {entry.get('entry_name')}")
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Capturadas", captured)
metric_b.metric("Pendientes", max(total_matches - captured, 0))
metric_c.metric("Total partidos", total_matches)

if is_global_prediction_lock_active(config):
    st.warning("La edición de predicciones ya está cerrada para esta fase.")
else:
    st.info(f"Puedes editar tus predicciones hasta {lock_at}. Después quedarán bloqueadas.")

filter_col1, filter_col2, filter_col3 = st.columns(3)
date_options = ["Todas"] + list(dict.fromkeys(matches["date_label"].tolist()))
group_options = ["Todos"] + sorted(matches["group_label"].dropna().unique().tolist())
date_filter = filter_col1.selectbox("Fecha", date_options)
group_filter = filter_col2.selectbox("Grupo", group_options)
status_filter = filter_col3.selectbox("Estado", ["Todos", "Pendientes", "Guardadas", "Bloqueadas"])

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
    st.info("No hay partidos para los filtros seleccionados.")
    st.stop()

for date_label in dict.fromkeys(row[1]["date_label"] for row in visible_rows):
    day_rows = [row for row in visible_rows if row[1]["date_label"] == date_label]
    st.subheader(date_label)
    for start in range(0, len(day_rows), 2):
        columns = st.columns(2)
        for column, (_, match, current_prediction, locked) in zip(columns, day_rows[start : start + 2]):
            with column:
                _render_match_card(
                    match.to_dict(),
                    current_prediction,
                    entry["entry_id"],
                    locked,
                    repo,
                )
