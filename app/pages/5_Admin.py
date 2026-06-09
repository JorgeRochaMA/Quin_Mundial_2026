"""Admin panel page."""

from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import pandas as pd
import streamlit as st

from components.layout import configure_page, render_sidebar, require_admin
from components.ui import info_card, metric_card, page_hero, section_header
from services.runtime import get_repository_or_stop
from utils.constants import (
    ENTRIES,
    MATCHES,
    PREDICTIONS,
    RESULTS,
    ROLE_ADMIN,
    STATUS_FINISHED,
    STATUS_LOCKED,
    STATUS_OPEN,
    USERS,
)
from utils.data import as_bool, as_float, as_int, clean_text
from utils.prizes import calculate_prizes, format_mxn
from utils.time import get_match_lock_state, normalize_match_status


def _clean_html(markup: str) -> str:
    """Remove indentation so Markdown does not render HTML as code."""
    return "\n".join(
        line.strip()
        for line in dedent(markup).strip().splitlines()
        if line.strip()
    )


def _html(markup: str) -> None:
    """Render HTML safely."""
    st.markdown(_clean_html(markup), unsafe_allow_html=True)


def _match_label(row: dict[str, Any]) -> str:
    """Build a readable match label for admin selection."""
    match_id = clean_text(row.get("match_id")) or "-"
    home = clean_text(row.get("home_team")) or "Local"
    away = clean_text(row.get("away_team")) or "Visitante"
    group = clean_text(row.get("group")) or "-"
    date = clean_text(row.get("match_date")) or "Sin fecha"

    return f"{match_id} · {home} vs {away} · Grupo {group} · {date}"


def _get_existing_result(results: pd.DataFrame, match_id: str) -> dict[str, Any] | None:
    """Return existing result for a match if present."""
    if results.empty or "match_id" not in results.columns:
        return None

    match = results[results["match_id"] == match_id]
    if match.empty:
        return None

    return match.iloc[0].to_dict()


def _normalized_match_status(value: Any) -> str:
    """Return a display-safe match status."""
    return normalize_match_status(value)


def _payment_label(value: Any) -> str:
    """Return a Spanish payment status label."""
    return "✅ Pagada" if as_bool(value) else "⏳ Pendiente"


def _count_finished_matches(matches: pd.DataFrame) -> int:
    """Count finished matches from MATCHES."""
    if matches.empty or "status" not in matches.columns:
        return 0

    return int(
        matches["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(str(STATUS_FINISHED).upper())
        .sum()
    )

def _build_admin_rankings(
    entries: pd.DataFrame,
    users: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Build a simple top ranking for the admin page."""
    if entries.empty:
        return pd.DataFrame(
            columns=[
                "position",
                "entry_name",
                "nickname",
                "total_points",
                "exact_scores",
                "predictions_count",
            ]
        )

    ranking = entries.copy()

    if "active" in ranking.columns:
        ranking = ranking[ranking["active"].apply(as_bool)]

    if ranking.empty:
        return pd.DataFrame(
            columns=[
                "position",
                "entry_name",
                "nickname",
                "total_points",
                "exact_scores",
                "predictions_count",
            ]
        )

    if not predictions.empty:
        pred = predictions.copy()
        pred["points"] = pred["points"].apply(lambda value: as_int(value, 0))

        totals = (
            pred.groupby("entry_id", as_index=False)
            .agg(
                total_points=("points", "sum"),
                exact_scores=("points", lambda values: int((values >= 5).sum())),
                predictions_count=("prediction_id", "count"),
            )
        )
    else:
        totals = pd.DataFrame(
            columns=["entry_id", "total_points", "exact_scores", "predictions_count"]
        )

    ranking = ranking.merge(totals, on="entry_id", how="left")

    for column in ["total_points", "exact_scores", "predictions_count"]:
        ranking[column] = ranking[column].fillna(0).astype(int)

    if not users.empty and "user_id" in users.columns:
        user_cols = users[["user_id", "nickname"]].copy()
        ranking = ranking.merge(user_cols, on="user_id", how="left")
    else:
        ranking["nickname"] = ""

    ranking["nickname"] = ranking["nickname"].fillna("Sin usuario")
    ranking = ranking.sort_values(
        by=["total_points", "exact_scores", "predictions_count", "created_at"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    ranking["position"] = ranking.index + 1

    return ranking[
        [
            "position",
            "entry_name",
            "nickname",
            "total_points",
            "exact_scores",
            "predictions_count",
        ]
    ]


def _render_admin_top_5(rankings: pd.DataFrame) -> None:
    """Render top 5 ranking in the admin page."""
    if rankings.empty:
        info_card(
            "Sin quinielas activas",
            "Cuando haya quinielas registradas, aquí aparecerá el top de la tabla general.",
            icon="🏆",
            accent="gold",
        )
        return

    top = rankings.head(5).copy()
    top = top.rename(
        columns={
            "position": "Posición",
            "entry_name": "Quiniela",
            "nickname": "Jugador",
            "total_points": "Puntos",
            "exact_scores": "Exactos",
            "predictions_count": "Predicciones",
        }
    )

    st.dataframe(
        top[
            [
                "Posición",
                "Quiniela",
                "Jugador",
                "Puntos",
                "Exactos",
                "Predicciones",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )

def _render_match_preview(match: dict[str, Any], existing_result: dict[str, Any] | None) -> None:
    """Render selected match context."""
    home = clean_text(match.get("home_team")) or "Local"
    away = clean_text(match.get("away_team")) or "Visitante"
    group = clean_text(match.get("group")) or "-"
    date = clean_text(match.get("match_date")) or "Sin fecha"
    city = clean_text(match.get("city")) or ""
    stadium = clean_text(match.get("stadium")) or ""
    status = _normalized_match_status(match.get("status"))

    score_text = "Sin resultado"
    if existing_result:
        score_text = f"{as_int(existing_result.get('home_score'), 0)} - {as_int(existing_result.get('away_score'), 0)}"

    location = " · ".join(part for part in [stadium, city] if part)

    _html(
        f"""
        <div class="qm-admin-match-card">
            <div class="qm-admin-match-meta">
                <span>Grupo {escape(group)}</span>
                <span>{escape(date)}</span>
                <span>{escape(status)}</span>
            </div>
            <div class="qm-admin-match-teams">
                <div>{escape(home)}</div>
                <div class="qm-admin-vs">VS</div>
                <div>{escape(away)}</div>
            </div>
            <div class="qm-admin-match-footer">
                <span>{escape(location or "Sede por confirmar")}</span>
                <strong>{escape(score_text)}</strong>
            </div>
        </div>
        """
    )


def _render_pct_status(total_pct: int) -> None:
    """Render percentage validation status."""
    if total_pct == 100:
        info_card(
            "Distribución válida",
            "Los porcentajes suman 100%. La bolsa puede guardarse correctamente.",
            icon="✅",
            accent="green",
        )
    else:
        info_card(
            "Revisar distribución",
            f"Los porcentajes suman {total_pct}%. Para guardar deben sumar exactamente 100%.",
            icon="⚠️",
            accent="red",
        )


configure_page("Admin")
admin_user = require_admin()

repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

admin_user_success = st.session_state.pop("admin_user_success", "")
if admin_user_success:
    st.success(admin_user_success)

admin_payment_success = st.session_state.pop("admin_payment_success", "")
if admin_payment_success:
    st.success(admin_payment_success)

matches = data[MATCHES]
entries = data[ENTRIES]
predictions = data[PREDICTIONS]
results = data[RESULTS]
users = data[USERS]

active_entries = 0
paid_entries = 0

if not entries.empty:
    active_entries = int(entries["active"].apply(as_bool).sum()) if "active" in entries.columns else len(entries)
    paid_entries = int(entries["paid"].apply(as_bool).sum()) if "paid" in entries.columns else active_entries

finished_matches = _count_finished_matches(matches)
total_matches = len(matches) if not matches.empty else 0
pending_matches = max(total_matches - finished_matches, 0)

current_entry_fee = int(as_float(config.get("entry_fee"), 200))
current_first_pct = int(as_float(config.get("first_place_percentage"), 0.60) * 100)
current_second_pct = int(as_float(config.get("second_place_percentage"), 0.30) * 100)
current_third_pct = int(as_float(config.get("third_place_percentage"), 0.10) * 100)

current_prizes = calculate_prizes(entries, config)

page_hero(
    "Panel de administración",
    "Captura resultados oficiales, recalcula puntos y controla la bolsa de premios.",
    eyebrow="Control de la quiniela",
    pills=[
        f"{total_matches} partidos",
        f"{finished_matches} finalizados",
        f"{paid_entries} quinielas pagadas",
        format_mxn(current_prizes["total_pool"]),
    ],
)

section_header(
    "Estado general",
    "Resumen operativo antes de capturar resultados o modificar la bolsa.",
)

status_cols = st.columns(4)

with status_cols[0]:
    metric_card("Partidos", str(total_matches), "Calendario cargado", "navy")

with status_cols[1]:
    metric_card("Finalizados", str(finished_matches), "Con resultado oficial", "green")

with status_cols[2]:
    metric_card("Pendientes", str(pending_matches), "Por actualizar", "gold")

with status_cols[3]:
    metric_card("Bolsa", format_mxn(current_prizes["total_pool"]), "Acumulada", "green")


result_col, config_col = st.columns([1.2, 1])

with result_col:
    section_header(
        "Actualizar resultado",
        "Selecciona un partido, captura el marcador oficial y recalcula la tabla.",
    )

    if matches.empty:
        info_card(
            "No hay partidos cargados",
            "Carga primero el calendario en la hoja MATCHES para poder capturar resultados.",
            icon="📅",
            accent="red",
        )
    else:
        match_records = matches.to_dict("records")
        labels = [_match_label(row) for row in match_records]

        selected_label = st.selectbox(
            "Partido",
            labels,
            help="Elige el partido que quieres actualizar.",
        )
        selected_index = labels.index(selected_label)
        selected_match = match_records[selected_index]
        selected_match_id = clean_text(selected_match.get("match_id"))

        existing_result = _get_existing_result(results, selected_match_id)

        _render_match_preview(selected_match, existing_result)

        default_home_score = as_int(existing_result.get("home_score"), 0) if existing_result else 0
        default_away_score = as_int(existing_result.get("away_score"), 0) if existing_result else 0

        with st.form("result_form"):
            score_left, score_middle, score_right = st.columns([1, 0.18, 1])

            with score_left:
                home_score = st.number_input(
                    f"Goles {selected_match.get('home_team')}",
                    min_value=0,
                    max_value=20,
                    value=default_home_score,
                )

            with score_middle:
                st.markdown(
                    "<div class='qm-admin-score-vs'>VS</div>",
                    unsafe_allow_html=True,
                )

            with score_right:
                away_score = st.number_input(
                    f"Goles {selected_match.get('away_team')}",
                    min_value=0,
                    max_value=20,
                    value=default_away_score,
                )

            save_result = st.form_submit_button(
                "Guardar resultado y recalcular",
                use_container_width=True,
            )

        if save_result:
            try:
                repo.upsert_result(selected_match["match_id"], home_score, away_score)
                repo.update_match_status(selected_match["match_id"], STATUS_FINISHED)
                updated = repo.recalculate_prediction_points()
                st.success(f"Resultado guardado. Predicciones recalculadas: {updated}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


with config_col:
    section_header(
        "Configuración de bolsa",
        "Ajusta el costo por quiniela y la distribución de premios.",
    )

    with st.form("pool_config_form"):
        entry_fee = st.number_input(
            "Costo por quiniela (MXN)",
            min_value=1,
            max_value=100000,
            value=current_entry_fee,
            step=50,
        )

        pct1, pct2, pct3 = st.columns(3)

        with pct1:
            first_pct = st.number_input(
                "1er lugar (%)",
                min_value=0,
                max_value=100,
                value=current_first_pct,
            )

        with pct2:
            second_pct = st.number_input(
                "2do lugar (%)",
                min_value=0,
                max_value=100,
                value=current_second_pct,
            )

        with pct3:
            third_pct = st.number_input(
                "3er lugar (%)",
                min_value=0,
                max_value=100,
                value=current_third_pct,
            )

        save_config = st.form_submit_button(
            "Guardar configuración",
            use_container_width=True,
        )

    total_pct = int(first_pct + second_pct + third_pct)

    preview_config = {
        **config,
        "entry_fee": str(entry_fee),
        "first_place_percentage": str(first_pct / 100),
        "second_place_percentage": str(second_pct / 100),
        "third_place_percentage": str(third_pct / 100),
    }

    prizes = calculate_prizes(entries, preview_config)

    _render_pct_status(total_pct)

    prize_cols = st.columns(2)

    with prize_cols[0]:
        metric_card("Quinielas activas", str(active_entries), "Entradas activas", "green")

    with prize_cols[1]:
        metric_card("Pagadas", str(paid_entries), "Aportan a bolsa", "gold")

    metric_card("Bolsa estimada", format_mxn(prizes["total_pool"]), "Según configuración actual", "navy")

    _html(
        f"""
        <div class="qm-admin-prize-list">
            <div>
                <span>🥇 1er lugar · {int(first_pct)}%</span>
                <strong>{escape(format_mxn(prizes["first_place"]))}</strong>
            </div>
            <div>
                <span>🥈 2do lugar · {int(second_pct)}%</span>
                <strong>{escape(format_mxn(prizes["second_place"]))}</strong>
            </div>
            <div>
                <span>🥉 3er lugar · {int(third_pct)}%</span>
                <strong>{escape(format_mxn(prizes["third_place"]))}</strong>
            </div>
        </div>
        """
    )

    if save_config:
        if total_pct != 100:
            st.error("Los porcentajes deben sumar 100%.")
        else:
            repo.update_config_values(
                {
                    "entry_fee": str(entry_fee),
                    "first_place_percentage": f"{first_pct / 100:.2f}",
                    "second_place_percentage": f"{second_pct / 100:.2f}",
                    "third_place_percentage": f"{third_pct / 100:.2f}",
                }
            )
            st.success("Configuración de bolsa guardada.")
            st.rerun()

section_header(
    "Gestionar estado de partidos",
    "Bloquea o desbloquea manualmente la captura de predicciones por partido.",
)

if matches.empty:
    info_card(
        "No hay partidos cargados",
        "Carga primero el calendario en MATCHES para gestionar estados.",
        icon="📅",
        accent="red",
    )
else:
    status_match_records = matches.to_dict("records")
    status_labels = [_match_label(row) for row in status_match_records]
    selected_status_label = st.selectbox(
        "Partido a gestionar",
        status_labels,
        help="Selecciona el partido que quieres abrir o bloquear.",
        key="admin_match_status_selector",
    )
    selected_status_index = status_labels.index(selected_status_label)
    selected_status_match = status_match_records[selected_status_index]
    selected_status_value = _normalized_match_status(selected_status_match.get("status"))

    info_card(
        "Estado actual",
        (
            f"{selected_status_value} · "
            f"{clean_text(selected_status_match.get('home_team')) or 'Local'} vs "
            f"{clean_text(selected_status_match.get('away_team')) or 'Visitante'}"
        ),
        icon="🔒" if selected_status_value == STATUS_LOCKED else "✅",
        accent="red" if selected_status_value == STATUS_LOCKED else "green",
    )

    status_options = [STATUS_OPEN, STATUS_LOCKED]
    status_index = status_options.index(selected_status_value) if selected_status_value in status_options else 0

    with st.form("match_status_form"):
        new_status = st.selectbox(
            "Nuevo estado",
            status_options,
            index=status_index,
            help="OPEN permite capturar si no hay resultado oficial ni cierre global. LOCKED bloquea manualmente.",
        )
        save_match_status = st.form_submit_button(
            "Guardar estado de partido",
            use_container_width=True,
        )

    if save_match_status:
        try:
            repo.update_match_status(selected_status_match["match_id"], new_status)
            st.success(f"Estado actualizado a {new_status}.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    diagnostic_match_id = clean_text(selected_status_match.get("match_id"))
    diagnostic_result = _get_existing_result(results, diagnostic_match_id)
    lock_state = get_match_lock_state(selected_status_match, config, diagnostic_result)
    has_user_prediction = False
    if not predictions.empty and "match_id" in predictions.columns:
        has_user_prediction = bool(
            predictions["match_id"].apply(clean_text).eq(diagnostic_match_id).any()
        )

    diagnostic = pd.DataFrame(
        [
            {
                "match_id": diagnostic_match_id,
                "raw_status": lock_state.raw_status,
                "normalized_status": lock_state.normalized_status,
                "has_official_result": "Sí" if lock_state.has_official_result else "No",
                "has_user_prediction": "Sí" if has_user_prediction else "No",
                "global_locked": "Sí" if lock_state.global_locked else "No",
                "locked": "Sí" if lock_state.locked else "No",
                "reason": lock_state.reason,
            }
        ]
    )

    st.caption("Diagnóstico de bloqueo: las predicciones existentes no bloquean partidos.")
    st.dataframe(diagnostic, hide_index=True, use_container_width=True)

section_header(
    "Gestión de usuarios",
    "Resetea contraseñas o elimina usuarios duplicados con sus quinielas y predicciones.",
)

if users.empty:
    info_card(
        "No hay usuarios cargados",
        "Cuando existan usuarios registrados, aquí podrás administrarlos.",
        icon="👤",
        accent="gold",
    )
else:
    user_records = users.to_dict("records")
    user_labels = [
        (
            f"{clean_text(user_row.get('nickname')) or 'Sin nickname'} · "
            f"{clean_text(user_row.get('role')) or 'USER'} · "
            f"{clean_text(user_row.get('user_id')) or '-'}"
        )
        for user_row in user_records
    ]

    selected_user_label = st.selectbox(
        "Usuario",
        user_labels,
        help="Selecciona el usuario que quieres administrar.",
        key="admin_user_selector",
    )
    selected_user = user_records[user_labels.index(selected_user_label)]
    selected_user_id = clean_text(selected_user.get("user_id"))
    selected_nickname = clean_text(selected_user.get("nickname")) or "Sin nickname"
    selected_role = clean_text(selected_user.get("role")).upper() or "USER"
    selected_is_admin = selected_role == ROLE_ADMIN
    selected_is_current_admin = selected_user_id == clean_text(admin_user.get("user_id"))

    selected_user_entries = pd.DataFrame()
    if not entries.empty and "user_id" in entries.columns:
        selected_user_entries = entries[entries["user_id"] == selected_user_id]

    selected_entry_ids = set()
    if not selected_user_entries.empty and "entry_id" in selected_user_entries.columns:
        selected_entry_ids = {
            clean_text(row.get("entry_id"))
            for _, row in selected_user_entries.iterrows()
            if clean_text(row.get("entry_id"))
        }

    selected_user_predictions = pd.DataFrame()
    if not predictions.empty and "entry_id" in predictions.columns:
        selected_user_predictions = predictions[
            predictions["entry_id"].apply(clean_text).isin(selected_entry_ids)
        ]

    reset_col, delete_col = st.columns(2)

    with reset_col:
        info_card(
            "Resetear contraseña",
            f"Usuario: {selected_nickname} · {selected_user_id}",
            icon="🔑",
            accent="green",
        )

        with st.form("admin_reset_user_password_form"):
            new_password = st.text_input("Nueva contraseña temporal", type="password")
            confirm_password = st.text_input("Confirmar contraseña", type="password")
            reset_password = st.form_submit_button(
                "Actualizar contraseña",
                use_container_width=True,
            )

        if reset_password:
            if not new_password:
                st.error("Escribe una nueva contraseña temporal.")
            elif len(new_password) < 4:
                st.error("La contraseña debe tener al menos 4 caracteres.")
            elif new_password != confirm_password:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    updated = repo.update_user_password(selected_user_id, new_password)
                    if updated:
                        st.session_state["admin_user_success"] = "Contraseña actualizada correctamente."
                        st.rerun()
                    else:
                        st.error("No se encontró el usuario seleccionado.")
                except ValueError as exc:
                    st.error(str(exc))

    with delete_col:
        info_card(
            "Eliminar usuario duplicado",
            (
                f"{selected_nickname} · {selected_user_id} · "
                f"{len(selected_user_entries)} quinielas · "
                f"{len(selected_user_predictions)} predicciones"
            ),
            icon="🗑️",
            accent="red",
        )

        delete_disabled = selected_is_admin or selected_is_current_admin
        if selected_is_admin:
            st.warning("Los usuarios ADMIN no se pueden eliminar desde esta acción.")

        confirm_delete_user = st.checkbox(
            "Confirmo que quiero eliminar este usuario, sus quinielas y sus predicciones.",
            key=f"confirm_delete_user_{selected_user_id}",
            disabled=delete_disabled,
        )

        if st.button(
            "Eliminar usuario",
            use_container_width=True,
            disabled=delete_disabled or not confirm_delete_user,
            type="secondary",
        ):
            try:
                deleted = repo.delete_user(selected_user_id)

                if not deleted:
                    st.error("No se encontró el usuario seleccionado.")
                    st.stop()

                if selected_is_current_admin:
                    st.session_state.clear()
                else:
                    st.session_state["admin_user_success"] = "Usuario eliminado correctamente."

                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

section_header(
    "Gestión de pagos",
    "Marca quinielas como pagadas o pendientes sin modificar el monto registrado.",
)

if entries.empty:
    info_card(
        "No hay quinielas registradas",
        "Cuando existan quinielas, aquí podrás administrar su estado de pago.",
        icon="💵",
        accent="gold",
    )
else:
    payment_entries = entries.copy()

    if "active" in payment_entries.columns:
        payment_entries = payment_entries[payment_entries["active"].apply(as_bool)]

    if payment_entries.empty:
        info_card(
            "Sin quinielas activas",
            "No hay entradas activas para administrar pagos.",
            icon="💵",
            accent="gold",
        )
    else:
        payment_labels = []

        for _, row in payment_entries.iterrows():
            entry_id = clean_text(row.get("entry_id"))
            entry_name = clean_text(row.get("entry_name")) or "Sin nombre"
            user_id = clean_text(row.get("user_id"))
            payment_status = "pagada" if as_bool(row.get("paid")) else "pendiente"

            nickname = "Sin usuario"
            if not users.empty and "user_id" in users.columns:
                user_match = users[users["user_id"] == user_id]
                if not user_match.empty:
                    nickname = clean_text(user_match.iloc[0].get("nickname")) or nickname

            payment_labels.append(
                {
                    "label": f"{entry_name} · {nickname} · {payment_status} · {entry_id}",
                    "entry_id": entry_id,
                    "entry_name": entry_name,
                    "nickname": nickname,
                    "paid": as_bool(row.get("paid")),
                }
            )

        selected_payment_label = st.selectbox(
            "Quiniela para pago",
            [item["label"] for item in payment_labels],
            help="Selecciona la quiniela cuyo pago quieres actualizar.",
            key="admin_payment_entry_selector",
        )
        selected_payment_entry = next(
            item for item in payment_labels if item["label"] == selected_payment_label
        )

        selected_entry_predictions = pd.DataFrame()
        if not predictions.empty and "entry_id" in predictions.columns:
            selected_entry_predictions = predictions[
                predictions["entry_id"].apply(clean_text).eq(selected_payment_entry["entry_id"])
            ]

        info_card(
            selected_payment_entry["entry_name"],
            (
                f"Jugador: {selected_payment_entry['nickname']} · "
                f"{len(selected_entry_predictions)} predicciones · "
                f"Pago: {_payment_label(selected_payment_entry['paid'])}"
            ),
            icon="💵",
            accent="green" if selected_payment_entry["paid"] else "gold",
        )

        next_paid_status = not selected_payment_entry["paid"]
        payment_button_label = (
            "Marcar como pendiente"
            if selected_payment_entry["paid"]
            else "Marcar como pagada"
        )

        if st.button(payment_button_label, use_container_width=True, type="secondary"):
            updated = repo.update_entry_payment_status(
                selected_payment_entry["entry_id"],
                next_paid_status,
            )

            if updated:
                st.session_state["admin_payment_success"] = "Estado de pago actualizado correctamente."
                st.rerun()
            else:
                st.error("No se encontró la quiniela seleccionada.")

section_header(
    "Gestión de quinielas",
    "Administra entradas creadas por error y revisa rápidamente el top de la tabla general.",
)

management_col, top_col = st.columns([1, 1.15])

with management_col:
    if entries.empty:
        info_card(
            "No hay quinielas para administrar",
            "Cuando los usuarios creen quinielas, aquí podrás revisarlas o eliminarlas.",
            icon="🎟️",
            accent="gold",
        )
    else:
        admin_entries = entries.copy()

        if "active" in admin_entries.columns:
            admin_entries = admin_entries[admin_entries["active"].apply(as_bool)]

        if admin_entries.empty:
            info_card(
                "Sin quinielas activas",
                "No hay entradas activas para administrar.",
                icon="🎟️",
                accent="gold",
            )
        else:
            entry_labels = []

            for _, row in admin_entries.iterrows():
                entry_id = clean_text(row.get("entry_id"))
                entry_name = clean_text(row.get("entry_name")) or "Sin nombre"
                user_id = clean_text(row.get("user_id"))
                amount_paid = as_int(row.get("amount_paid"), 0)
                created_at = clean_text(row.get("created_at"))

                nickname = "Sin usuario"
                if not users.empty and "user_id" in users.columns:
                    user_match = users[users["user_id"] == user_id]
                    if not user_match.empty:
                        nickname = clean_text(user_match.iloc[0].get("nickname")) or nickname

                entry_labels.append(
                    {
                        "label": f"{entry_name} · {nickname} · {format_mxn(amount_paid)} · {entry_id}",
                        "entry_id": entry_id,
                        "entry_name": entry_name,
                        "nickname": nickname,
                        "created_at": created_at,
                    }
                )

            selected_entry_label = st.selectbox(
                "Quiniela",
                [item["label"] for item in entry_labels],
                help="Selecciona la quiniela que quieres revisar o eliminar.",
            )

            selected_entry = next(
                item for item in entry_labels if item["label"] == selected_entry_label
            )

            info_card(
                selected_entry["entry_name"],
                f"Jugador: {selected_entry['nickname']} · Creada: {selected_entry['created_at'] or 'Sin fecha'}",
                icon="🎟️",
                accent="gold",
            )

            confirm_delete = st.checkbox(
                "Confirmo que quiero eliminar esta quiniela y sus predicciones.",
                key="confirm_delete_entry",
            )

            if st.button(
                "Eliminar quiniela",
                use_container_width=True,
                disabled=not confirm_delete,
                type="secondary",
            ):
                deleted = repo.delete_entry(selected_entry["entry_id"])

                if deleted:
                    st.success("Quiniela eliminada correctamente.")
                    st.rerun()
                else:
                    st.error("No se pudo eliminar la quiniela seleccionada.")

with top_col:
    rankings = _build_admin_rankings(entries, users, predictions)

    info_card(
        "Top 5 general",
        "Vista rápida de las quinielas mejor posicionadas hasta este momento.",
        icon="🏆",
        accent="green",
    )

    _render_admin_top_5(rankings)
