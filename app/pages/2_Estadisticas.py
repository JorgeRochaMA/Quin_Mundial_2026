"""Social prediction insights page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from components.ui import empty_state, info_card, metric_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import AWAY_WIN, DRAW, ENTRIES, HOME_WIN, MATCHES, PREDICTIONS
from utils.data import as_bool, as_int, clean_text


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


def _format_pct(value: float) -> str:
    """Render a percentage value."""
    return f"{value:.0%}"


def _match_label(row: pd.Series) -> str:
    """Return a readable match label."""
    home_team = clean_text(row.get("home_team")) or "Local"
    away_team = clean_text(row.get("away_team")) or "Visitante"
    return f"{home_team} vs {away_team}"


def _scoreline(row: pd.Series) -> str:
    """Return a prediction scoreline label."""
    home_goals = row.get("pred_home_goals")
    away_goals = row.get("pred_away_goals")
    if pd.isna(home_goals) or pd.isna(away_goals):
        return "-"
    return f"{as_int(home_goals)} - {as_int(away_goals)}"


def _active_predictions(
    entries: pd.DataFrame,
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Return predictions from active entries joined with match context."""
    if entries.empty or predictions.empty:
        return pd.DataFrame()

    active_entries = entries.copy()
    if "active" in active_entries:
        active_entries = active_entries[active_entries["active"].apply(as_bool)]

    if active_entries.empty:
        return pd.DataFrame()

    scoped = predictions.merge(
        active_entries[["entry_id"]],
        on="entry_id",
        how="inner",
    )
    if scoped.empty:
        return pd.DataFrame()

    scoped = scoped.copy()
    scoped["scoreline"] = scoped.apply(_scoreline, axis=1)
    scoped["predicted_goals"] = (
        pd.to_numeric(scoped["pred_home_goals"], errors="coerce").fillna(0)
        + pd.to_numeric(scoped["pred_away_goals"], errors="coerce").fillna(0)
    )

    if matches.empty:
        return scoped

    return scoped.merge(
        matches[
            [
                "match_id",
                "match_date",
                "group",
                "home_team",
                "away_team",
            ]
        ],
        on="match_id",
        how="left",
    )


def _popular_score(predictions: pd.DataFrame) -> tuple[str, int]:
    """Return the most repeated scoreline and its count."""
    if predictions.empty:
        return "Sin datos", 0

    score_counts = (
        predictions[predictions["scoreline"] != "-"]
        .groupby("scoreline", as_index=False)
        .agg(predictions=("prediction_id", "count"))
        .sort_values(["predictions", "scoreline"], ascending=[False, True])
    )
    if score_counts.empty:
        return "Sin datos", 0

    top = score_counts.iloc[0]
    return clean_text(top.get("scoreline")) or "Sin datos", as_int(top.get("predictions"), 0)


def _winner_choices(predictions: pd.DataFrame) -> pd.DataFrame:
    """Return rows where a concrete team was selected as winner."""
    rows = []
    for _, row in predictions.iterrows():
        selected_result = clean_text(row.get("selected_result"))
        if selected_result == HOME_WIN:
            team = clean_text(row.get("home_team")) or "Local"
        elif selected_result == AWAY_WIN:
            team = clean_text(row.get("away_team")) or "Visitante"
        else:
            continue

        rows.append(
            {
                "group": clean_text(row.get("group")) or "-",
                "team": team,
                "prediction_id": row.get("prediction_id"),
            }
        )

    return pd.DataFrame(rows)


def _top_winner_team(predictions: pd.DataFrame) -> tuple[str, int]:
    """Return the team most selected as winner."""
    winners = _winner_choices(predictions)
    if winners.empty:
        return "Sin datos", 0

    top = (
        winners.groupby("team", as_index=False)
        .agg(times=("prediction_id", "count"))
        .sort_values(["times", "team"], ascending=[False, True])
        .iloc[0]
    )
    return clean_text(top.get("team")) or "Sin datos", as_int(top.get("times"), 0)


def _popular_score_by_match(predictions: pd.DataFrame) -> dict[str, str]:
    """Return most common scoreline by match_id."""
    if predictions.empty:
        return {}

    score_counts = (
        predictions[predictions["scoreline"] != "-"]
        .groupby(["match_id", "scoreline"], as_index=False)
        .agg(predictions=("prediction_id", "count"))
        .sort_values(["match_id", "predictions", "scoreline"], ascending=[True, False, True])
    )
    if score_counts.empty:
        return {}

    return score_counts.drop_duplicates("match_id").set_index("match_id")["scoreline"].to_dict()


def _match_prediction_counts(matches: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    """Return HOME/DRAW/AWAY counts and percentages for every match."""
    if matches.empty:
        return pd.DataFrame()

    rows = []
    popular_scores = _popular_score_by_match(predictions)
    grouped = {}
    if not predictions.empty:
        grouped = {
            match_id: group
            for match_id, group in predictions.groupby("match_id")
        }

    for _, match in matches.iterrows():
        match_id = clean_text(match.get("match_id"))
        match_predictions = grouped.get(match_id, pd.DataFrame())
        total = len(match_predictions)
        home_count = 0
        draw_count = 0
        away_count = 0
        if total:
            counts = match_predictions["selected_result"].apply(clean_text).value_counts().to_dict()
            home_count = as_int(counts.get(HOME_WIN), 0)
            draw_count = as_int(counts.get(DRAW), 0)
            away_count = as_int(counts.get(AWAY_WIN), 0)

        home_pct = home_count / total if total else 0
        draw_pct = draw_count / total if total else 0
        away_pct = away_count / total if total else 0
        values = {
            HOME_WIN: home_pct,
            DRAW: draw_pct,
            AWAY_WIN: away_pct,
        }
        favorite_key = max(values, key=values.get) if total else ""
        home_team = clean_text(match.get("home_team")) or "Local"
        away_team = clean_text(match.get("away_team")) or "Visitante"
        if favorite_key == HOME_WIN:
            favorite_label = home_team
            rival_pct = away_pct
        elif favorite_key == AWAY_WIN:
            favorite_label = away_team
            rival_pct = home_pct
        elif favorite_key == DRAW:
            favorite_label = "Empate"
            rival_pct = max(home_pct, away_pct)
        else:
            favorite_label = "Sin predicciones"
            rival_pct = 0

        rows.append(
            {
                "match_id": match_id,
                "Fecha": _short_date(match.get("match_date")),
                "Grupo": clean_text(match.get("group")) or "-",
                "Partido": _match_label(match),
                "Favorito según predicciones": favorite_label,
                "% favorito": _format_pct(max(values.values()) if total else 0),
                "% empate": _format_pct(draw_pct),
                "% rival": _format_pct(rival_pct),
                "% local": _format_pct(home_pct),
                "% visitante": _format_pct(away_pct),
                "Marcador más popular": popular_scores.get(match_id, "-"),
                "_total": total,
                "_spread": max(values.values()) - min(values.values()) if total else 1,
            }
        )

    return pd.DataFrame(rows)


def _group_favorites(matches: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    """Return team winner-pick rankings by group."""
    if matches.empty:
        return pd.DataFrame()

    team_rows = []
    for _, match in matches.iterrows():
        group = clean_text(match.get("group")) or "-"
        for column in ["home_team", "away_team"]:
            team = clean_text(match.get(column))
            if team:
                team_rows.append({"Grupo": group, "Equipo": team})

    teams = pd.DataFrame(team_rows).drop_duplicates()
    if teams.empty:
        return pd.DataFrame()

    winners = _winner_choices(predictions)
    winner_counts = pd.DataFrame(columns=["Grupo", "Equipo", "Veces elegido ganador"])
    if not winners.empty:
        winner_counts = (
            winners.rename(columns={"group": "Grupo", "team": "Equipo"})
            .groupby(["Grupo", "Equipo"], as_index=False)
            .agg(**{"Veces elegido ganador": ("prediction_id", "count")})
        )

    group_totals = pd.DataFrame(columns=["Grupo", "_group_predictions"])
    if not predictions.empty and "group" in predictions:
        group_totals = (
            predictions.assign(Grupo=predictions["group"].apply(lambda value: clean_text(value) or "-"))
            .groupby("Grupo", as_index=False)
            .agg(_group_predictions=("prediction_id", "count"))
        )

    table = teams.merge(winner_counts, on=["Grupo", "Equipo"], how="left")
    table = table.merge(group_totals, on="Grupo", how="left")
    table["Veces elegido ganador"] = table["Veces elegido ganador"].fillna(0).astype(int)
    table["_group_predictions"] = table["_group_predictions"].fillna(0).astype(int)
    table["% sobre predicciones posibles del grupo"] = table.apply(
        lambda row: _format_pct(
            row["Veces elegido ganador"] / row["_group_predictions"]
            if row["_group_predictions"]
            else 0
        ),
        axis=1,
    )
    table = table.sort_values(
        ["Grupo", "Veces elegido ganador", "Equipo"],
        ascending=[True, False, True],
    )
    table["Ranking dentro del grupo"] = (
        table.groupby("Grupo")["Veces elegido ganador"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    return table[
        [
            "Grupo",
            "Equipo",
            "Veces elegido ganador",
            "% sobre predicciones posibles del grupo",
            "Ranking dentro del grupo",
        ]
    ]


def _least_supported_teams(group_favorites: pd.DataFrame) -> pd.DataFrame:
    """Return the least picked teams as winners."""
    if group_favorites.empty:
        return pd.DataFrame()

    return (
        group_favorites[["Equipo", "Grupo", "Veces elegido ganador"]]
        .sort_values(["Veces elegido ganador", "Grupo", "Equipo"], ascending=[True, True, True])
        .head(10)
    )


configure_page("Estadísticas")
require_login()

repo = get_repository_or_stop()
data = repo.load_data()
render_sidebar(data)

entries = data[ENTRIES]
matches = data[MATCHES]
predictions = _active_predictions(entries, matches, data[PREDICTIONS])
total_entries = 0
if not entries.empty:
    total_entries = int(entries["active"].apply(as_bool).sum()) if "active" in entries else len(entries)
total_predictions = len(predictions)
total_matches = len(matches)
popular_score, popular_score_count = _popular_score(predictions)
top_winner, top_winner_count = _top_winner_team(predictions)
avg_goals = 0
if not predictions.empty:
    avg_goals = predictions.groupby("match_id")["predicted_goals"].mean().mean()
match_counts = _match_prediction_counts(matches, predictions)
group_favorites = _group_favorites(matches, predictions)
least_supported = _least_supported_teams(group_favorites)

most_divided_label = "Sin datos"
if not match_counts.empty:
    divided_candidates = match_counts[match_counts["_total"] > 0].sort_values(
        ["_spread", "_total", "Partido"],
        ascending=[True, False, True],
    )
    if not divided_candidates.empty:
        most_divided = divided_candidates.iloc[0]
        most_divided_label = clean_text(most_divided.get("Partido")) or "Sin datos"

page_hero(
    "Estadísticas",
    "Insights sociales de las predicciones capturadas por los participantes.",
    eyebrow="Lectura del grupo",
    pills=[
        f"{total_entries} quinielas activas",
        f"{total_predictions} predicciones",
        f"{total_matches} partidos",
    ],
)

info_card(
    "Predicciones, no resultados oficiales",
    "Estas estadísticas reflejan las predicciones capturadas por los participantes, no resultados oficiales.",
    icon="📊",
    accent="navy",
)

divided_table = pd.DataFrame()
if not match_counts.empty:
    divided_table = (
        match_counts[match_counts["_total"] > 0]
        .sort_values(["_spread", "_total", "Partido"], ascending=[True, False, True])
        .head(10)
    )

summary_tab, favoritism_tab, groups_tab, players_tab, post_match_tab = st.tabs(
    [
        "Resumen social",
        "Favoritismo",
        "Grupos",
        "Jugadores",
        "Post partido",
    ]
)

with summary_tab:
    section_header(
        "Resumen social",
        "Una lectura rápida de los patrones más fuertes de la quiniela.",
    )

    if predictions.empty:
        empty_state(
            "Aún no hay predicciones suficientes",
            "Cuando los participantes capturen marcadores, aquí aparecerán las tendencias del grupo.",
            icon="📈",
        )
    else:
        card_cols = st.columns(5)
        with card_cols[0]:
            metric_card("Predicciones", str(total_predictions), "Capturadas", "green")
        with card_cols[1]:
            metric_card(
                "Marcador popular",
                popular_score,
                f"{popular_score_count} veces",
                "gold",
            )
        with card_cols[2]:
            metric_card(
                "Equipo favorito",
                top_winner,
                f"{top_winner_count} elecciones",
                "navy",
            )
        with card_cols[3]:
            metric_card("Partido dividido", most_divided_label, "Más equilibrado", "red")
        with card_cols[4]:
            metric_card(
                "Prom. goles",
                f"{avg_goals:.1f}",
                "Pronosticados por partido",
                "green",
            )

with favoritism_tab:
    section_header(
        "Favoritismo por partido",
        "Qué resultado domina en cada partido según las predicciones capturadas.",
    )

    if match_counts.empty:
        empty_state(
            "Aún no hay partidos cargados",
            "Cuando exista calendario, aquí aparecerá el favoritismo por partido.",
            icon="⚽",
        )
    else:
        st.dataframe(
            match_counts[
                [
                    "Fecha",
                    "Grupo",
                    "Partido",
                    "Favorito según predicciones",
                    "% favorito",
                    "% empate",
                    "% rival",
                    "Marcador más popular",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

    section_header(
        "Partidos más divididos",
        "Top 10 de partidos donde las predicciones están más equilibradas.",
    )

    if divided_table.empty:
        empty_state(
            "Aún no hay partidos divididos",
            "Se calcularán cuando existan predicciones capturadas por partido.",
            icon="⚖️",
        )
    else:
        st.dataframe(
            divided_table[
                [
                    "Partido",
                    "Grupo",
                    "% local",
                    "% empate",
                    "% visitante",
                    "Marcador más popular",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

with groups_tab:
    section_header(
        "Favoritos por grupo",
        "Ranking de equipos por veces que fueron elegidos como ganadores.",
    )

    if group_favorites.empty:
        empty_state(
            "Aún no hay favoritos por grupo",
            "Se calcularán cuando existan selecciones de ganador por equipo.",
            icon="🏆",
        )
    else:
        st.dataframe(group_favorites, hide_index=True, use_container_width=True)

    section_header(
        "Equipos menos respaldados",
        "Top 10 de equipos con menos elecciones como ganador.",
    )

    if least_supported.empty:
        empty_state(
            "Aún no hay datos suficientes",
            "Cuando existan predicciones, aquí aparecerán los equipos menos elegidos.",
            icon="📉",
        )
    else:
        st.dataframe(least_supported, hide_index=True, use_container_width=True)

with players_tab:
    empty_state(
        "Próximamente: estilos de predicción por jugador.",
        "Este espacio se usará para analizar patrones de participantes en una siguiente versión.",
        icon="👤",
    )

with post_match_tab:
    empty_state(
        "Disponible cuando el admin capture resultados oficiales.",
        "Aquí vivirán quinielazos, favoritos que cumplieron y sorpresas del torneo.",
        icon="🏟️",
    )
