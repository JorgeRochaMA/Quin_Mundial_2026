"""Dashboard page."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, PREDICTIONS, RESULTS, USERS
from utils.data import as_bool, as_float, as_int, clean_text
from utils.prizes import calculate_prizes, format_mxn
from utils.rankings import build_rankings


def _percent_label(value: float) -> str:
    """Render a decimal percentage for dashboard cards."""
    return f"{value:.0%}"


def _dashboard_card(label: str, value: str, detail: str, accent: str = "green") -> None:
    """Render a compact dashboard card."""
    st.markdown(
        f"""
        <div class="qm-dashboard-card qm-accent-{accent}">
            <div class="qm-dashboard-label">{escape(label)}</div>
            <div class="qm-dashboard-value">{escape(value)}</div>
            <div class="qm-dashboard-detail">{escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _finished_matches_count(results: pd.DataFrame) -> int:
    """Count matches with official scores captured."""
    if results.empty:
        return 0
    finished = results[
        results["home_score"].apply(clean_text).ne("")
        & results["away_score"].apply(clean_text).ne("")
    ]
    return len(finished["match_id"].drop_duplicates())


def _render_podium(rankings: pd.DataFrame) -> None:
    """Render a compact preview of the top available entries."""
    if rankings.empty:
        st.info("Aún no hay ranking disponible. Cuando se registren quinielas, el podio aparecerá aquí.")
        return

    top_entries = rankings.head(3)
    columns = st.columns(len(top_entries))
    medals = {1: "Oro", 2: "Plata", 3: "Bronce"}
    accents = {1: "gold", 2: "green", 3: "navy"}
    for column, (_, row) in zip(columns, top_entries.iterrows()):
        position = as_int(row.get("position"), 0)
        with column:
            st.markdown(
                f"""
                <div class="qm-podium-card qm-accent-{accents.get(position, "green")}">
                    <div class="qm-podium-rank">#{position} · {escape(medals.get(position, "Lugar"))}</div>
                    <div class="qm-podium-name">{escape(clean_text(row.get("entry_name")) or "Quiniela")}</div>
                    <div class="qm-podium-user">{escape(clean_text(row.get("nickname")) or "Sin apodo")}</div>
                    <div class="qm-podium-points">{as_int(row.get("total_points"), 0)} pts</div>
                    <div class="qm-dashboard-detail">{as_int(row.get("exact_scores"), 0)} exactos</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_rankings(rankings: pd.DataFrame) -> None:
    """Render real rankings with Spanish labels and subtle winner highlighting."""
    if rankings.empty:
        st.info("Todavía no hay quinielas registradas. Cuando haya participantes, aquí aparecerá la tabla general.")
        return

    table = rankings.rename(
        columns={
            "position": "Posición",
            "entry_name": "Quiniela",
            "nickname": "Nickname",
            "total_points": "Puntos",
            "exact_scores": "Marcadores exactos",
            "predictions_count": "Predicciones",
        }
    )
    columns = [
        "Posición",
        "Quiniela",
        "Nickname",
        "Puntos",
        "Marcadores exactos",
        "Predicciones",
    ]

    def highlight_winner(row: pd.Series) -> list[str]:
        position = as_int(row.get("Posición"), 0)
        if position == 1:
            return ["background-color: #fff8df; font-weight: 800;"] * len(row)
        return [""] * len(row)

    styled = table[columns].style.apply(highlight_winner, axis=1)
    st.dataframe(styled, hide_index=True, use_container_width=True)


configure_page("Dashboard")
require_login()
repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

entries = data[ENTRIES]
users = data[USERS]
rankings = build_rankings(entries, users, data[PREDICTIONS], data[RESULTS])
prizes = calculate_prizes(entries, config)

phase_label = config.get("current_phase_label", "Fase de grupos")
phase_total_matches = as_int(config.get("current_phase_total_matches"), 72)
phase_groups = as_int(config.get("current_phase_groups"), 12)
played_matches = min(_finished_matches_count(data[RESULTS]), phase_total_matches)
remaining_matches = max(phase_total_matches - played_matches, 0)
active_entries = 0 if entries.empty else int(entries["active"].apply(as_bool).sum())
total_users = 0 if users.empty else int(users["active"].apply(as_bool).sum())
entry_fee = as_float(config.get("entry_fee"), 200)
first_pct = as_float(config.get("first_place_percentage"), 0.60)
second_pct = as_float(config.get("second_place_percentage"), 0.30)
third_pct = as_float(config.get("third_place_percentage"), 0.10)
paid_entries = 0
if not entries.empty and "paid" in entries:
    paid_entries = int((entries["active"].apply(as_bool) & entries["paid"].apply(as_bool)).sum())

st.markdown(
    f"""
    <section class="qm-dashboard-hero">
        <div class="qm-hero-content">
            <p class="qm-hero-kicker">Panel de la quiniela</p>
            <h1>Quiniela Mundial 2026</h1>
            <p class="qm-hero-subtitle">{escape(phase_label)} · {phase_total_matches} partidos · {phase_groups} grupos</p>
            <div class="qm-pill-row">
                <span>{escape(phase_label)}</span>
                <span>{phase_total_matches} partidos</span>
                <span>Máximo 5 pts por partido</span>
                <span>{format_mxn(entry_fee)} por quiniela</span>
            </div>
        </div>
        <div class="qm-hero-prize-panel">
            <div class="qm-prize-eyebrow">Bolsa acumulada</div>
            <div class="qm-prize-total">{format_mxn(prizes["total_pool"])}</div>
            <div class="qm-prize-meta">{active_entries} quinielas activas · {paid_entries} pagadas</div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Estado de la quiniela")
state_cols = st.columns(6)
state_cards = [
    ("Participantes", str(total_users), "Usuarios activos", "green"),
    ("Quinielas", str(active_entries), f"{paid_entries} pagadas", "gold"),
    ("Bolsa", format_mxn(prizes["total_pool"]), "Acumulada", "gold"),
    ("Costo", format_mxn(entry_fee), "Por quiniela", "navy"),
    ("Jugados", str(played_matches), "Con resultado", "green"),
    ("Pendientes", str(remaining_matches), "Por jugar", "red"),
]
for column, (label, value, detail, accent) in zip(state_cols, state_cards):
    with column:
        _dashboard_card(label, value, detail, accent)

st.markdown("### Reglas de puntuación")
rule_cols = st.columns(4)
rules = [
    ("🎯", "3 pts", "Acierta ganador o empate", "gold"),
    ("⚽", "+2 pts", "Marcador exacto", "green"),
    ("🏆", "5 pts", "Máximo por partido", "navy"),
    ("—", "0 pts", "Predicción incorrecta", "red"),
]
for column, (icon, value, detail, accent) in zip(rule_cols, rules):
    with column:
        st.markdown(
            f"""
            <div class="qm-rule-card qm-accent-{accent}">
                <div class="qm-rule-icon">{icon}</div>
                <div class="qm-dashboard-value">{value}</div>
                <div class="qm-dashboard-detail">{detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("### Premios actuales")
prize_cols = st.columns(3)
prize_cards = [
    ("1er lugar · " + _percent_label(first_pct), prizes["first_place"], "Campeón de la quiniela", "gold"),
    ("2do lugar · " + _percent_label(second_pct), prizes["second_place"], "Subcampeón", "green"),
    ("3er lugar · " + _percent_label(third_pct), prizes["third_place"], "Tercer puesto", "navy"),
]
for column, (place, amount, detail, accent) in zip(prize_cols, prize_cards):
    with column:
        _dashboard_card(place, format_mxn(amount), detail, accent)

st.markdown("### Podio de la tabla")
_render_podium(rankings)

st.markdown("### Tabla general")
_render_rankings(rankings)
