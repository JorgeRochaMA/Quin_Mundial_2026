"""Stats page."""

from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from components.ui import empty_state, info_card, metric_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, MATCHES, PREDICTIONS, RESULTS, USERS
from utils.data import as_int, clean_text
from utils.stats import build_pool_stats


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


def _safe_entry_name(value: dict[str, Any] | None) -> str:
    """Return a safe entry name from a stats record."""
    if not value:
        return "Sin datos"
    return clean_text(value.get("entry_name")) or "Sin datos"


def _render_insight_card(
    title: str,
    value: str,
    caption: str,
    icon: str,
    accent: str = "green",
) -> None:
    """Render a compact insight card."""
    _html(
        f"""
        <div class="qm-insight-card qm-accent-{escape(accent)}">
            <div class="qm-insight-icon">{escape(icon)}</div>
            <div class="qm-insight-title">{escape(title)}</div>
            <div class="qm-insight-value">{escape(value)}</div>
            <div class="qm-insight-caption">{escape(caption)}</div>
        </div>
        """
    )


def _render_group_table(group_summary) -> None:
    """Render group summary table with Spanish labels."""
    display = group_summary.rename(
        columns={
            "group": "Grupo",
            "avg_points": "Puntos promedio",
            "predictions": "Predicciones",
            "exact_scores": "Exactos",
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
    )


configure_page("Estadísticas")
require_login()

repo = get_repository_or_stop()
data = repo.load_data()
render_sidebar(data)

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
group_summary = stats["group_summary"]

total_entries = len(data[ENTRIES]) if not data[ENTRIES].empty else 0
total_predictions = len(data[PREDICTIONS]) if not data[PREDICTIONS].empty else 0
finished_matches = (
    len(data[RESULTS]["match_id"].dropna().unique())
    if not data[RESULTS].empty and "match_id" in data[RESULTS].columns
    else 0
)

page_hero(
    "Estadísticas",
    "Lee tendencias, comportamiento y patrones de la quiniela conforme avanza el Mundial.",
    eyebrow="Insights de la quiniela",
    pills=[
        f"{total_entries} quinielas",
        f"{total_predictions} predicciones",
        f"{finished_matches} partidos con resultado",
    ],
)

section_header(
    "Resumen inteligente",
    "Estas métricas se actualizan conforme se capturan predicciones y resultados oficiales.",
)

summary_cols = st.columns(3)

with summary_cols[0]:
    metric_card("Quinielas", str(total_entries), "Entradas registradas", "green")

with summary_cols[1]:
    metric_card("Predicciones", str(total_predictions), "Marcadores capturados", "gold")

with summary_cols[2]:
    metric_card("Resultados", str(finished_matches), "Partidos finalizados", "navy")


section_header(
    "Highlights",
    "Una lectura rápida de quién va destacando y cómo se comportan las predicciones.",
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    if most_exact:
        _render_insight_card(
            title="Más exactos",
            value=_safe_entry_name(most_exact),
            caption=f"{as_int(most_exact.get('exact_scores'), 0)} marcadores exactos",
            icon="🎯",
            accent="green",
        )
    else:
        _render_insight_card(
            title="Más exactos",
            value="Sin datos",
            caption="Aún no hay exactos calculados",
            icon="🎯",
            accent="green",
        )

with col2:
    if best_accuracy:
        _render_insight_card(
            title="Mejor efectividad",
            value=_safe_entry_name(best_accuracy),
            caption=f"{best_accuracy['accuracy']:.0%} de efectividad",
            icon="📈",
            accent="gold",
        )
    else:
        _render_insight_card(
            title="Mejor efectividad",
            value="Sin datos",
            caption="Se calculará con resultados oficiales",
            icon="📈",
            accent="gold",
        )

with col3:
    if riskiest:
        _render_insight_card(
            title="Más arriesgada",
            value=_safe_entry_name(riskiest),
            caption=f"{riskiest['avg_predicted_goals']:.1f} goles promedio",
            icon="🔥",
            accent="red",
        )
    else:
        _render_insight_card(
            title="Más arriesgada",
            value="Sin datos",
            caption="Según promedio de goles pronosticados",
            icon="🔥",
            accent="red",
        )

with col4:
    if popular_score:
        _render_insight_card(
            title="Marcador favorito",
            value=clean_text(popular_score.get("scoreline")) or "Sin datos",
            caption=f"{as_int(popular_score.get('predictions'), 0)} veces repetido",
            icon="⚽",
            accent="navy",
        )
    else:
        _render_insight_card(
            title="Marcador favorito",
            value="Sin datos",
            caption="Aún no hay marcador dominante",
            icon="⚽",
            accent="navy",
        )


info_card(
    "Cómo leer estas estadísticas",
    "La quiniela más arriesgada se calcula por promedio de goles pronosticados. La mejor efectividad depende de resultados oficiales ya capturados.",
    icon="💡",
    accent="navy",
)

section_header(
    "Rendimiento por grupo",
    "Compara cómo se están comportando las predicciones en cada grupo.",
)

if group_summary.empty:
    empty_state(
        "Aún no hay resultados suficientes",
        "Cuando captures resultados oficiales, aquí aparecerá el rendimiento por grupo.",
        icon="📊",
    )
else:
    _render_group_table(group_summary)