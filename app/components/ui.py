"""Reusable visual helpers for Streamlit pages."""

from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


def _accent_class(accent: str) -> str:
    """Return a safe accent CSS class."""
    allowed = {"green", "gold", "navy", "red"}
    selected = accent if accent in allowed else "green"
    return f"qm-accent-{selected}"


def _render_pills(pills: Iterable[str] | None) -> str:
    """Render pill HTML for compact page metadata."""
    if not pills:
        return ""
    items = "".join(f"<span>{escape(str(pill))}</span>" for pill in pills)
    return f'<div class="qm-pill-row">{items}</div>'


def section_header(title: str, subtitle: str | None = None, eyebrow: str | None = None) -> None:
    """Render a compact section heading."""
    eyebrow_html = f'<div class="qm-section-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f'<p class="qm-section-subtitle">{escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="qm-section-header">
            {eyebrow_html}
            <h2>{escape(title)}</h2>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, caption: str | None = None, accent: str = "green") -> None:
    """Render a reusable metric card."""
    caption_html = f'<div class="qm-dashboard-detail">{escape(caption)}</div>' if caption else ""
    st.markdown(
        f"""
        <div class="qm-dashboard-card {_accent_class(accent)}">
            <div class="qm-dashboard-label">{escape(label)}</div>
            <div class="qm-dashboard-value">{escape(str(value))}</div>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_card(title: str, body: str, icon: str | None = None, accent: str = "green") -> None:
    """Render an informational card."""
    icon_html = f'<div class="qm-info-icon">{escape(icon)}</div>' if icon else ""
    st.markdown(
        f"""
        <div class="qm-info-card {_accent_class(accent)}">
            {icon_html}
            <div>
                <div class="qm-info-title">{escape(title)}</div>
                <div class="qm-info-body">{escape(body)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, message: str, icon: str = "ℹ️") -> None:
    """Render a friendly empty state."""
    st.markdown(
        f"""
        <div class="qm-empty-state">
            <div class="qm-empty-icon">{escape(icon)}</div>
            <div class="qm-empty-title">{escape(title)}</div>
            <div class="qm-empty-message">{escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(text: str, accent: str = "green") -> None:
    """Render a standalone status pill."""
    st.markdown(
        f'<span class="qm-status-pill {_accent_class(accent)}">{escape(text)}</span>',
        unsafe_allow_html=True,
    )


def page_hero(
    title: str,
    subtitle: str | None = None,
    eyebrow: str | None = None,
    pills: Iterable[str] | None = None,
) -> None:
    """Render a compact premium page hero."""
    eyebrow_html = f'<p class="qm-hero-kicker">{escape(eyebrow)}</p>' if eyebrow else ""
    subtitle_html = f'<p class="qm-hero-subtitle">{escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
        <section class="qm-page-hero">
            <div class="qm-hero-content">
                {eyebrow_html}
                <h1>{escape(title)}</h1>
                {subtitle_html}
                {_render_pills(pills)}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
