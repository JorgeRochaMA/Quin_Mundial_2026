"""Dashboard page."""

from __future__ import annotations

from html import escape
from textwrap import dedent

import pandas as pd
import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, PREDICTIONS, RESULTS, USERS
from utils.data import as_bool, as_float, as_int, clean_text
from utils.prizes import calculate_prizes, format_mxn
from utils.rankings import build_rankings


def _clean_html(markup: str) -> str:
    """Remove indentation so Markdown does not render HTML as a code block."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).strip().splitlines()
        if line.strip()
    )


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
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    labels = {1: "Oro", 2: "Plata", 3: "Bronce"}
    items = []
    for _, row in top_entries.iterrows():
        position = as_int(row.get("position"), 0)
        first_class = " qm-podium-item-first" if position == 1 else ""
        items.append(
            f"""
            <div class="qm-podium-item{first_class}">
                <div class="qm-podium-medal">{escape(medals.get(position, "🏅"))}</div>
                <div class="qm-podium-main">
                    <div class="qm-podium-rank">#{position} · {escape(labels.get(position, "Lugar"))}</div>
                    <div class="qm-podium-name">{escape(clean_text(row.get("entry_name")) or "Quiniela")}</div>
                    <div class="qm-podium-user">{escape(clean_text(row.get("nickname")) or "Sin apodo")}</div>
                </div>
                <div class="qm-podium-stats">
                    <strong>{as_int(row.get("total_points"), 0)} pts</strong>
                    <span>{as_int(row.get("exact_scores"), 0)} exactos · {as_int(row.get("predictions_count"), 0)} predicciones</span>
                </div>
            </div>
            """
        )

    st.markdown(
        _clean_html(
            f"""
        <section class="qm-podium-panel">
            {"".join(items)}
        </section>
        """
        ),
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
st.caption("Resumen rápido de participación, bolsa y avance de partidos.")
st.markdown(
    f"""
    <section class="qm-status-panel">
        <div class="qm-status-panel-item">
            <span class="qm-status-panel-icon">👥</span>
            <span>
                <strong>{total_users}</strong>
                <small>Participantes</small>
            </span>
        </div>
        <div class="qm-status-panel-item">
            <span class="qm-status-panel-icon">🎟️</span>
            <span>
                <strong>{paid_entries}/{active_entries}</strong>
                <small>Pagadas / activas</small>
            </span>
        </div>
        <div class="qm-status-panel-item qm-status-panel-money">
            <span class="qm-status-panel-icon">💰</span>
            <span>
                <strong>{format_mxn(prizes["total_pool"])}</strong>
                <small>Bolsa acumulada</small>
            </span>
        </div>
        <div class="qm-status-panel-item">
            <span class="qm-status-panel-icon">💵</span>
            <span>
                <strong>{format_mxn(entry_fee)}</strong>
                <small>Costo por quiniela</small>
            </span>
        </div>
        <div class="qm-status-panel-item">
            <span class="qm-status-panel-icon">⚽</span>
            <span>
                <strong>{played_matches}</strong>
                <small>Partidos jugados</small>
            </span>
        </div>
        <div class="qm-status-panel-item">
            <span class="qm-status-panel-icon">⏳</span>
            <span>
                <strong>{remaining_matches}</strong>
                <small>Partidos pendientes</small>
            </span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Reglas de puntuación")
st.caption("Puntaje por partido capturado.")
st.markdown(
    """
    <section class="qm-compact-panel qm-rules-panel">
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🎯</span>
            <span>
                <strong>3 pts</strong>
                <small>Acierta ganador o empate</small>
            </span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">⚽</span>
            <span>
                <strong>+2 pts</strong>
                <small>Marcador exacto</small>
            </span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">🏆</span>
            <span>
                <strong>5 pts</strong>
                <small>Máximo por partido</small>
            </span>
        </div>
        <div class="qm-compact-panel-item">
            <span class="qm-status-panel-icon">—</span>
            <span>
                <strong>0 pts</strong>
                <small>Predicción incorrecta</small>
            </span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Premios actuales")
st.caption("Distribución actual de la bolsa acumulada.")
st.markdown(
    f"""
    <section class="qm-compact-panel qm-prizes-panel">
        <div class="qm-compact-panel-item qm-compact-money">
            <span class="qm-status-panel-icon">🥇</span>
            <span>
                <strong>{format_mxn(prizes["first_place"])}</strong>
                <small>1er lugar · {_percent_label(first_pct)}</small>
            </span>
        </div>
        <div class="qm-compact-panel-item qm-compact-money">
            <span class="qm-status-panel-icon">🥈</span>
            <span>
                <strong>{format_mxn(prizes["second_place"])}</strong>
                <small>2do lugar · {_percent_label(second_pct)}</small>
            </span>
        </div>
        <div class="qm-compact-panel-item qm-compact-money">
            <span class="qm-status-panel-icon">🥉</span>
            <span>
                <strong>{format_mxn(prizes["third_place"])}</strong>
                <small>3er lugar · {_percent_label(third_pct)}</small>
            </span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Podio de la tabla")
_render_podium(rankings)

st.markdown("### Tabla general")
_render_rankings(rankings)
