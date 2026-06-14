"""Live ranking page."""

from __future__ import annotations

from html import escape
from textwrap import dedent

import pandas as pd
import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from components.ui import empty_state
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, MATCHES, PREDICTIONS, RESULTS, USERS
from utils.data import as_bool, as_float, as_int, clean_text
from utils.prizes import calculate_prizes, format_mxn
from utils.rankings import build_rankings
from utils.scoring import is_exact_score, result_from_score


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


def _winner_label(home_team: str, away_team: str, home_score: int, away_score: int) -> str:
    """Return the official winner label."""
    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team
    return "Empate"


def _render_official_results(matches: pd.DataFrame, results: pd.DataFrame) -> None:
    """Render official match results captured by admins."""
    if matches.empty or results.empty:
        empty_state(
            "Aún no hay resultados oficiales",
            "Cuando el admin capture marcadores, aquí aparecerán.",
            icon="⚽",
        )
        return

    scored_results = results[
        results["home_score"].apply(clean_text).ne("")
        & results["away_score"].apply(clean_text).ne("")
    ].copy()

    if scored_results.empty:
        empty_state(
            "Aún no hay resultados oficiales",
            "Cuando el admin capture marcadores, aquí aparecerán.",
            icon="⚽",
        )
        return

    merged = matches.merge(scored_results, on="match_id", how="inner")

    if merged.empty:
        empty_state(
            "Aún no hay resultados oficiales",
            "Cuando el admin capture marcadores, aquí aparecerán.",
            icon="⚽",
        )
        return

    merged["_parsed_date"] = pd.to_datetime(merged["match_date"], errors="coerce")
    merged = merged.sort_values(
        ["_parsed_date", "match_id"],
        ascending=[False, False],
        na_position="last",
    )

    table = pd.DataFrame(
        [
            {
                "Fecha": _short_date(row.get("match_date")),
                "Partido": (
                    f"{clean_text(row.get('home_team')) or 'Local'}"
                    f" vs {clean_text(row.get('away_team')) or 'Visitante'}"
                ),
                "Marcador": f"{as_int(row.get('home_score'), 0)} - {as_int(row.get('away_score'), 0)}",
                "Ganador / Empate": _winner_label(
                    clean_text(row.get("home_team")) or "Local",
                    clean_text(row.get("away_team")) or "Visitante",
                    as_int(row.get("home_score"), 0),
                    as_int(row.get("away_score"), 0),
                ),
            }
            for _, row in merged.iterrows()
        ]
    )

    st.dataframe(table, hide_index=True, use_container_width=True)


def _official_matches(matches: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    """Return matches joined with official scores."""
    if matches.empty or results.empty:
        return pd.DataFrame()

    scored_results = results[
        results["home_score"].apply(clean_text).ne("")
        & results["away_score"].apply(clean_text).ne("")
    ].copy()

    if scored_results.empty:
        return pd.DataFrame()

    scored_results = scored_results.drop_duplicates("match_id", keep="last")
    merged = matches.merge(scored_results, on="match_id", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged["_parsed_date"] = pd.to_datetime(merged["match_date"], errors="coerce")
    return merged.sort_values(
        ["_parsed_date", "match_id"],
        ascending=[False, False],
        na_position="last",
    )


def _build_accuracy_radiography(
    entries: pd.DataFrame,
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    results: pd.DataFrame,
) -> pd.DataFrame:
    """Build visual post-match accuracy metrics without changing scoring."""
    official_matches = _official_matches(matches, results)
    if official_matches.empty:
        return pd.DataFrame()

    if entries.empty or predictions.empty:
        scoped_predictions = pd.DataFrame(columns=predictions.columns)
    else:
        active_entries = entries.copy()
        if "active" in active_entries:
            active_entries = active_entries[active_entries["active"].apply(as_bool)]
        active_entry_ids = set(active_entries["entry_id"].apply(clean_text))
        scoped_predictions = predictions[
            predictions["entry_id"].apply(clean_text).isin(active_entry_ids)
        ].copy()

    rows = []
    for _, match in official_matches.iterrows():
        match_id = clean_text(match.get("match_id"))
        home_team = clean_text(match.get("home_team")) or "Local"
        away_team = clean_text(match.get("away_team")) or "Visitante"
        home_score = as_int(match.get("home_score"), 0)
        away_score = as_int(match.get("away_score"), 0)
        official_result = result_from_score(home_score, away_score)

        match_predictions = pd.DataFrame()
        if not scoped_predictions.empty:
            match_predictions = scoped_predictions[
                scoped_predictions["match_id"].apply(clean_text).eq(match_id)
            ]

        total_predictions = len(match_predictions)
        result_hits = 0
        exact_hits = 0
        if not match_predictions.empty:
            result_hits = int(
                match_predictions["selected_result"]
                .apply(lambda value: clean_text(value) == official_result)
                .sum()
            )
            exact_hits = int(
                match_predictions.apply(
                    lambda row: is_exact_score(
                        row.get("pred_home_goals"),
                        row.get("pred_away_goals"),
                        home_score,
                        away_score,
                    ),
                    axis=1,
                ).sum()
            )

        rows.append(
            {
                "match_id": match_id,
                "Fecha": _short_date(match.get("match_date")),
                "Partido": f"{home_team} vs {away_team}",
                "Marcador oficial": f"{home_score} - {away_score}",
                "Aciertos resultado": result_hits,
                "Marcadores exactos": exact_hits,
                "total_predictions": total_predictions,
                "_parsed_date": match.get("_parsed_date"),
            }
        )

    return pd.DataFrame(rows)


def _render_accuracy_bars(radiography: pd.DataFrame) -> None:
    """Render compact horizontal accuracy bars."""
    rows = []
    for _, row in radiography.iterrows():
        total_predictions = as_int(row.get("total_predictions"), 0)
        result_hits = as_int(row.get("Aciertos resultado"), 0)
        exact_hits = as_int(row.get("Marcadores exactos"), 0)
        result_pct = 0 if total_predictions <= 0 else min(100, (result_hits / total_predictions) * 100)
        exact_pct = 0 if total_predictions <= 0 else min(100, (exact_hits / total_predictions) * 100)
        rows.append(
            f"""
            <div class="qm-accuracy-row">
                <div class="qm-accuracy-match">
                    <strong>{escape(clean_text(row.get("Partido")) or "Partido")}</strong>
                    <span>{escape(clean_text(row.get("Fecha")) or "-")} · Marcador {escape(clean_text(row.get("Marcador oficial")) or "-")} · {total_predictions} predicciones</span>
                </div>
                <div class="qm-accuracy-bars">
                    <div class="qm-accuracy-bar-line">
                        <span>Resultado</span>
                        <div class="qm-accuracy-track">
                            <div class="qm-accuracy-fill qm-accuracy-fill-result" style="width: {result_pct:.1f}%"></div>
                        </div>
                        <strong>{result_hits}</strong>
                    </div>
                    <div class="qm-accuracy-bar-line">
                        <span>Exactos</span>
                        <div class="qm-accuracy-track">
                            <div class="qm-accuracy-fill qm-accuracy-fill-exact" style="width: {exact_pct:.1f}%"></div>
                        </div>
                        <strong>{exact_hits}</strong>
                    </div>
                </div>
            </div>
            """
        )

    st.markdown(
        _clean_html(
            f"""
            <section class="qm-accuracy-panel">
                {"".join(rows)}
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


def _render_accuracy_radiography(
    entries: pd.DataFrame,
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    results: pd.DataFrame,
) -> None:
    """Render post-match accuracy insights."""
    radiography = _build_accuracy_radiography(entries, matches, predictions, results)
    if radiography.empty:
        empty_state(
            "Radiografía pendiente",
            "Cuando se capturen resultados oficiales, aquí aparecerá la radiografía de aciertos.",
            icon="📊",
        )
        return

    hardest = radiography.sort_values(
        ["Marcadores exactos", "Aciertos resultado", "Partido"],
        ascending=[True, True, True],
    ).iloc[0]

    st.markdown(
        f"""
        <section class="qm-status-panel qm-status-panel-four">
            <div class="qm-status-panel-item">
                <span class="qm-status-panel-icon">✅</span>
                <span>
                    <strong>{len(radiography)}</strong>
                    <small>Partidos oficiales</small>
                </span>
            </div>
            <div class="qm-status-panel-item">
                <span class="qm-status-panel-icon">🎯</span>
                <span>
                    <strong>{int(radiography["Aciertos resultado"].sum())}</strong>
                    <small>Aciertos de resultado</small>
                </span>
            </div>
            <div class="qm-status-panel-item qm-status-panel-money">
                <span class="qm-status-panel-icon">🏆</span>
                <span>
                    <strong>{int(radiography["Marcadores exactos"].sum())}</strong>
                    <small>Marcadores exactos</small>
                </span>
            </div>
            <div class="qm-status-panel-item qm-status-panel-wrap">
                <span class="qm-status-panel-icon">🧩</span>
                <span>
                    <strong>{escape(clean_text(hardest.get("Partido")) or "-")}</strong>
                    <small>Partido más difícil</small>
                </span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    _render_accuracy_bars(radiography)


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


configure_page("Ranking en vivo")
require_login()
repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

entries = data[ENTRIES]
matches = data[MATCHES]
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
            <p class="qm-hero-kicker">Ranking en vivo</p>
            <h1>Ranking en vivo</h1>
            <p class="qm-hero-subtitle">Seguimiento de la Quiniela Mundial 2026 · {escape(phase_label)} · {phase_total_matches} partidos</p>
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

st.markdown("### Resultados oficiales")
st.caption("Partidos con marcador oficial capturado.")
_render_official_results(matches, data[RESULTS])

st.markdown("### Radiografía de aciertos")
st.caption("Qué tan bien leyó la quiniela cada partido con resultado oficial.")
_render_accuracy_radiography(entries, matches, data[PREDICTIONS], data[RESULTS])
