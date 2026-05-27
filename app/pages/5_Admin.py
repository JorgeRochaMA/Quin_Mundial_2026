"""Admin panel page."""

from __future__ import annotations

import streamlit as st

from components.layout import configure_page, render_sidebar, require_admin
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, MATCHES, STATUS_FINISHED
from utils.data import as_bool, as_float
from utils.prizes import calculate_prizes, format_mxn


configure_page("Admin")
require_admin()
repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

st.title("Panel de administración")
st.caption("Captura resultados oficiales y controla la bolsa de premios.")

result_col, config_col = st.columns(2)

with result_col:
    st.subheader("Actualizar resultado")
    st.caption("Al guardar, el partido se marca como finalizado y se recalculan los puntos.")
    matches = data[MATCHES]
    if matches.empty:
        st.info("No hay partidos cargados en MATCHES.")
    else:
        labels = [
            f"{row['match_id']} · {row['home_team']} vs {row['away_team']} · {row['match_date']}"
            for _, row in matches.iterrows()
        ]
        selected_label = st.selectbox("Partido", labels)
        selected_index = labels.index(selected_label)
        selected_match = matches.iloc[selected_index].to_dict()

        with st.form("result_form"):
            col1, col2 = st.columns(2)
            home_score = col1.number_input(
                f"Goles {selected_match.get('home_team')}",
                min_value=0,
                max_value=20,
                value=0,
            )
            away_score = col2.number_input(
                f"Goles {selected_match.get('away_team')}",
                min_value=0,
                max_value=20,
                value=0,
            )
            save_result = st.form_submit_button("Guardar resultado y recalcular", use_container_width=True)

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
    st.subheader("Configuración de bolsa")
    st.caption("Ajusta el costo por quiniela y cómo se reparte la bolsa.")

    active_entries = 0
    entries = data[ENTRIES]
    if not entries.empty:
        active_entries = int(entries["active"].apply(as_bool).sum())

    with st.form("pool_config_form"):
        entry_fee = st.number_input(
            "Costo por quiniela (MXN)",
            min_value=1,
            max_value=100000,
            value=int(as_float(config.get("entry_fee"), 200)),
            step=50,
        )
        pct1, pct2, pct3 = st.columns(3)
        first_pct = pct1.number_input(
            "1er lugar (%)",
            min_value=0,
            max_value=100,
            value=int(as_float(config.get("first_place_percentage"), 0.60) * 100),
        )
        second_pct = pct2.number_input(
            "2do lugar (%)",
            min_value=0,
            max_value=100,
            value=int(as_float(config.get("second_place_percentage"), 0.30) * 100),
        )
        third_pct = pct3.number_input(
            "3er lugar (%)",
            min_value=0,
            max_value=100,
            value=int(as_float(config.get("third_place_percentage"), 0.10) * 100),
        )
        save_config = st.form_submit_button("Guardar configuración", use_container_width=True)

    preview_config = {
        **config,
        "entry_fee": str(entry_fee),
        "first_place_percentage": str(first_pct / 100),
        "second_place_percentage": str(second_pct / 100),
        "third_place_percentage": str(third_pct / 100),
    }
    prizes = calculate_prizes(entries, preview_config)
    st.metric("Quinielas activas", active_entries)
    st.metric("Bolsa estimada", format_mxn(prizes["total_pool"]))
    st.write(
        f"Premios actuales: 1ro {format_mxn(prizes['first_place'])} · "
        f"2do {format_mxn(prizes['second_place'])} · "
        f"3ro {format_mxn(prizes['third_place'])}"
    )

    if save_config:
        total_pct = first_pct + second_pct + third_pct
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
