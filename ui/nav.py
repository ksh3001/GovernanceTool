"""Navigation helpers shared by the pages: header bar, footer, hint and the page-switch callback."""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st


def header(*trail: str, mode: str = "") -> None:
    """Top bar: where the user is (left) and who is signed in and in which mode (right)."""
    crumbs = ' <span class="sep">›</span> '.join(
        f'<span class="here">{html.escape(p)}</span>' if i == len(trail) - 1 else html.escape(p)
        for i, p in enumerate(trail))
    pills = [f'<span class="pill">📅 {datetime.now().strftime("%b %d, %Y")}</span>']
    if user := st.session_state.get("user"):
        pills.append(f'<span class="pill">👤 {html.escape(user)}</span>')
    if mode:
        pills.append(f'<span class="pill">LLM: {html.escape(mode)}</span>')
    st.markdown(f'<div class="appbar"><div class="crumbs">{crumbs}</div><div class="pills">{"".join(pills)}</div></div>',
                unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        '<div class="appfooter">'
        '<span>🛡️ <b>Provenix</b> · POC-Lite</span>'
        '<span>Findings support a compliance review and are not legal advice. '
        'The compliance score is an internal metric, not an official EU rating.</span>'
        '<span>Light or dark theme: top-right menu ⋮ › Settings</span>'
        '</div>', unsafe_allow_html=True)


def hint(text: str) -> None:
    """A quiet one-line callout that tells the user what to do next."""
    st.markdown(f'<div class="hint">{text}</div>', unsafe_allow_html=True)


def go(page: str, app_id: str | None = None) -> None:
    """Button callback: switch page ('home', 'onboard', 'app', 'frameworks')."""
    if page == "frameworks":
        st.session_state.framework_confirmed = False
        return
    st.session_state.page = page
    if app_id:
        st.session_state.app_id = app_id
