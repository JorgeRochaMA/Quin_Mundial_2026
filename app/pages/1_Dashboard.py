"""Dashboard page."""

from __future__ import annotations

import streamlit as st

from components.layout import configure_page, render_sidebar, require_login
from components.tables import show_rankings_table
from services.runtime import get_repository_or_stop
from utils.constants import ENTRIES, USERS
from utils.data import as_bool, as_int
from utils.prizes import calculate_prizes, format_mxn
from utils.rankings import build_rankings


configure_page("Dashboard")
user = require_login()
repo = get_repository_or_stop()
data = repo.load_data()
config = repo.get_config()
render_sidebar(data)

entries = data[ENTRIES]
users = data[USERS]
rankings = build_rankings(entries, users, data["PREDICTIONS"], data["RESULTS"])
prizes = calculate_prizes(entries, config)

st.title("Dashboard")
phase_label = config.get("current_phase_label", "Fase de grupos")
phase_total_matches = as_int(config.get("current_phase_total_matches"), 72)
phase_groups = as_int(config.get("current_phase_groups"), 12)
played_matches = 0 if rankings.empty else int(rankings["played_matches"].max())
remaining_matches = max(phase_total_matches - played_matches, 0)
st.caption(f"{phase_label}: {phase_total_matches} partidos · {phase_groups} grupos")

active_entries = 0 if entries.empty else int(entries["active"].apply(as_bool).sum())
total_users = 0 if users.empty else int(users["active"].apply(as_bool).sum())

col1, col2 = st.columns(2)
col1.metric("Usuarios", total_users)
col2.metric("Quinielas", active_entries)

phase_col1, phase_col2, phase_col3 = st.columns(3)
phase_col1.metric("Partidos de fase", phase_total_matches)
phase_col2.metric("Partidos jugados", played_matches)
phase_col3.metric("Partidos por jugar", remaining_matches)

st.subheader("Premios actuales")
first, second, third = st.columns(3)
first.metric("1er lugar", format_mxn(prizes["first_place"]))
second.metric("2do lugar", format_mxn(prizes["second_place"]))
third.metric("3er lugar", format_mxn(prizes["third_place"]))

st.subheader("Tabla general")
show_rankings_table(rankings)
