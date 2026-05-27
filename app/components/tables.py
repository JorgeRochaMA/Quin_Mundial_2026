"""Table formatting helpers for Streamlit pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def show_rankings_table(rankings: pd.DataFrame, limit: int | None = None) -> None:
    """Render standings with Spanish column labels."""
    if rankings.empty:
        st.info("Todavía no hay quinielas registradas.")
        return

    table = rankings.copy()
    if limit:
        table = table.head(limit)
    table = table.rename(
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
    ]
    columns.append("Predicciones")
    st.dataframe(
        table[columns],
        hide_index=True,
        use_container_width=True,
    )
