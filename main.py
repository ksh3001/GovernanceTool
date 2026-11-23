"""Provenix POC-Lite entry point: streamlit run main.py"""
from __future__ import annotations

import hmac

import streamlit as st

from core.config import ROOT, load_settings
from core.overview import build_overview
from core.packs import discover_packs
from core.store import Store
from ui import app_page, home, onboarding, style
from ui import components as ui
from ui.nav import footer, go, header

st.set_page_config(page_title="Provenix", page_icon="🛡️", layout="wide")

style.apply()


@st.cache_resource
def services():
    settings = load_settings()
    return settings, Store(settings.data_dir)


settings, store = services()


def sign_in() -> None:
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown(
            '<div class="hero"><div class="brand">🛡️ Provenix</div><h1>Know your AI is compliant before the regulator asks.</h1>'
            '<div class="tag-line">Onboard an AI application, let the questionnaire choose the rules, assess the code '
            'against them, and sign off a report with every finding traced to evidence.</div>'
            '<div class="feat"><span class="fi">🧭</span><span><b>Questionnaire-driven scope.</b> Rules apply by risk tier, role and answers, each with a reason.</span></div>'
            '<div class="feat"><span class="fi">🔎</span><span><b>Evidence you can check.</b> Every finding cites exact file lines.</span></div>'
            '<div class="feat"><span class="fi">✍️</span><span><b>People stay in charge.</b> Confirm or override, with an audit trail.</span></div>'
            '</div>', unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            st.subheader("Sign in")
            st.caption("Your name is recorded on every review decision.")
            with st.form("signin", border=False):
                name = st.text_input("Your name")
                password = st.text_input("Demo password", type="password") if settings.demo_password else ""
                submitted = st.form_submit_button("Continue", type="primary", width="stretch")
            if submitted:
                if not name.strip():
                    st.error("Please enter your name.")
                elif settings.demo_password and not hmac.compare_digest(password, settings.demo_password):
                    st.error("Incorrect password.")
                else:
                    st.session_state.user = name.strip()
                    st.rerun()


def framework_picker() -> None:
    st.title("Choose a framework")
    st.caption("Pick one or more frameworks to assess your application against.")
    packs = discover_packs(settings.packs_dir)
    selected = set(st.session_state.get("frameworks", []))
    cols = st.columns(3)
    for i, pack in enumerate(packs):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(pack.name)
                if pack.available:
                    tag = "tag-ok" if pack.status == "reviewed" else "tag-draft"
                    label = "Expert reviewed" if pack.status == "reviewed" else "Draft, pending expert review"
                    st.markdown(f'<span class="tag {tag}">{label}</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="tag tag-soon">Coming soon</span>', unsafe_allow_html=True)
                st.markdown(f'<p class="muted">{pack.description}</p>', unsafe_allow_html=True)
                if pack.source:
                    st.caption(f"{pack.source} · v{pack.version}")
                if st.checkbox("Assess against this", key=f"pick_{pack.id}",
                               value=pack.id in selected, disabled=not pack.available):
                    selected.add(pack.id)
                else:
                    selected.discard(pack.id)
    st.session_state.frameworks = sorted(selected)
    st.write("")
    if st.button("Continue", type="primary", disabled=not selected):
        st.session_state.framework_confirmed = True
        st.rerun()


def sidebar_top() -> None:
    """Brand, profile and the main menu. Pages add their own section below this."""
    with st.sidebar:
        st.markdown('<div class="brand">🛡️ Provenix</div>', unsafe_allow_html=True)
        st.caption("AI governance assessment")
        st.markdown(ui.profile(st.session_state.user), unsafe_allow_html=True)
        if not st.session_state.get("framework_confirmed"):
            return
        page = st.session_state.get("page", "home")
        st.markdown('<div class="navlabel">Main</div>', unsafe_allow_html=True)
        for label, target, active in (("📊  Overview", "home", page in ("home", "app")),
                                      ("➕  Onboard an application", "onboard", page == "onboard")):
            st.button(label, key=f"nav_{target}", width="stretch", type="primary" if active else "secondary",
                      on_click=go, args=(target,))


def sidebar_bottom(overview) -> None:
    with st.sidebar:
        if st.session_state.get("framework_confirmed"):
            st.markdown('<div class="navlabel">More</div>', unsafe_allow_html=True)
            st.button("🧭  Frameworks", key="nav_frameworks", width="stretch", on_click=go, args=("frameworks",))
            names = {p.id: p.name for p in discover_packs(settings.packs_dir)}
            chips = "".join(f'<span class="chip">{ui.E(names.get(f, f))}</span>' for f in st.session_state.get("frameworks", []))
            reviewed, total = overview.reviewed, overview.total
            st.markdown(
                '<div class="sidecard"><div class="t">Review progress</div>'
                + (ui.meter(100 * reviewed / total) + f'<div style="margin-top:.35rem">{reviewed} of {total} findings reviewed</div>'
                   if total else '<div>No assessments yet.</div>')
                + f'<div style="margin-top:.5rem">{chips}</div></div>', unsafe_allow_html=True)
        if st.button("Sign out", width="stretch"):
            st.session_state.clear()
            st.rerun()


if "user" not in st.session_state:
    sign_in()
else:
    apps = store.list_apps()
    overview = build_overview(store, apps, settings.packs_dir)
    sidebar_top()
    if st.session_state.get("framework_confirmed"):
        if st.session_state.get("page") == "onboard":
            header("Applications", "Onboard an application", mode=settings.llm_mode)
            onboarding.render(store)
        elif st.session_state.get("page") == "app":
            app_page.render(store, settings, st.session_state.app_id)
        else:
            home.render(store, settings, overview, apps)
    else:
        framework_picker()
    sidebar_bottom(overview)
footer()
