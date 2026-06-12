"""Cookie helpers for persistent login."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from utils.data import clean_text


REMEMBER_COOKIE_NAME = "quiniela_session_token"


def get_remember_cookie() -> str:
    """Return the persistent login cookie token if present."""
    try:
        return clean_text(st.context.cookies.get(REMEMBER_COOKIE_NAME))
    except Exception:
        return ""


def render_set_remember_cookie(token: str, expires_at: str, reload_parent: bool = True) -> None:
    """Render a client-side script that stores the persistent login cookie."""
    token_json = json.dumps(clean_text(token))
    name_json = json.dumps(REMEMBER_COOKIE_NAME)
    expires_json = json.dumps(clean_text(expires_at))
    reload_script = "setTimeout(() => window.parent.location.reload(), 150);" if reload_parent else ""

    components.html(
        f"""
        <script>
        const cookieName = {name_json};
        const token = {token_json};
        const expiresAt = new Date({expires_json}).toUTCString();
        const secure = window.parent.location.protocol === "https:" ? "; Secure" : "";
        const cookieValue = `${{cookieName}}=${{encodeURIComponent(token)}}; expires=${{expiresAt}}; path=/; SameSite=Lax${{secure}}`;
        let cookieWritten = false;
        try {{
            window.parent.document.cookie = cookieValue;
            cookieWritten = true;
        }} catch (error) {{
            cookieWritten = false;
        }}
        if (!cookieWritten) {{
            try {{
                document.cookie = cookieValue;
            }} catch (error) {{}}
        }}
        {reload_script}
        </script>
        """,
        height=0,
    )


def render_clear_remember_cookie(reload_parent: bool = False) -> None:
    """Render a client-side script that clears the persistent login cookie."""
    name_json = json.dumps(REMEMBER_COOKIE_NAME)
    reload_script = "setTimeout(() => window.parent.location.reload(), 150);" if reload_parent else ""

    components.html(
        f"""
        <script>
        const cookieName = {name_json};
        const secure = window.parent.location.protocol === "https:" ? "; Secure" : "";
        const cookieValue = `${{cookieName}}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax${{secure}}`;
        let cookieCleared = false;
        try {{
            window.parent.document.cookie = cookieValue;
            cookieCleared = true;
        }} catch (error) {{
            cookieCleared = false;
        }}
        if (!cookieCleared) {{
            try {{
                document.cookie = cookieValue;
            }} catch (error) {{}}
        }}
        {reload_script}
        </script>
        """,
        height=0,
    )
