"""Provenix POC-Lite entry point: streamlit run main.py"""
from __future__ import annotations

import hmac

import streamlit as st

from core.config import ROOT, load_settings
from core.onboarding import load_questionnaire
from core.packs import discover_packs
from core.samples import install_samples
from core.tiers import load_classifier
from core.store import Store
from ui import app_page, onboarding

st.set_page_config(page_title="Provenix", page_icon="🛡️", layout="wide")

CSS = """
<style>
  .block-container {padding-top: 2rem; max-width: 1100px;}
  h1, h2, h3 {letter-spacing: -0.02em;}
  .brand {font-size: 1.4rem; font-weight: 700; color: #4F46E5;}
  .tag {display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem;
        font-weight: 600; margin-right: 6px;}
  .tag-draft {background:#FEF3C7; color:#92400E;}
  .tag-ok {background:#DCFCE7; color:#166534;}
  .tag-soon {background:#E2E8F0; color:#475569;}
  .muted {color:#64748B; font-size:.9rem;}
  .cv {font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:.82rem;
       border:1px solid #E2E8F0; border-radius:8px; overflow-x:auto; background:#fff; margin:.25rem 0;}
  .cv .row {display:flex;}
  .cv .n {min-width:3rem; text-align:right; padding:0 .6rem; color:#94A3B8; background:#F1F5F9; user-select:none;}
  .cv .t {white-space:pre; padding:0 .6rem; flex:1;}
  .cv .hit {background:#DCFCE7;}
  .cv .claim {background:#FEF3C7;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def services():
    settings = load_settings()
    return settings, Store(settings.data_dir)


settings, store = services()


def sign_in() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="brand">🛡️ Provenix</div>', unsafe_allow_html=True)
        st.title("Sign in")
        st.caption("Your name is recorded on every review decision.")
        with st.form("signin"):
            name = st.text_input("Your name")
            password = st.text_input("Demo password", type="password") if settings.demo_password else ""
            submitted = st.form_submit_button("Continue", type="primary", use_container_width=True)
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


TIER_STYLE = {"prohibited": "#B91C1C", "high": "#C2410C", "limited": "#A16207",
              "minimal": "#15803D", "out_of_scope": "#475569"}


def show_tier(app, questionnaire) -> None:
    """Risk-tier badge and the rule that set it, for each framework that has tier rules."""
    for fw in app.frameworks:
        classify = load_classifier(settings.packs_dir / fw)
        if classify is None:
            continue
        result = classify(questionnaire)
        colour = TIER_STYLE.get(result.tier, "#475569")
        st.markdown(f'<span class="tag" style="background:{colour};color:#fff">{result.label}</span> '
                    f'<span class="muted">{result.legal_basis}</span>', unsafe_allow_html=True)
        with st.expander("Why this tier?"):
            st.write(result.reason)
            for step in result.steps:
                st.markdown(f"{'✅' if step.matched else '▫️'} {step.question}"
                            + (f" — _{step.detail}_" if step.detail else ""))
            st.caption(f"Rule `{result.rule_id}` · [Regulation (EU) 2024/1689]({result.source_url})")


def home() -> None:
    packs = {p.id: p.name for p in discover_packs(settings.packs_dir)}
    st.title("Applications")
    st.caption("Frameworks: " + ", ".join(packs[f] for f in st.session_state.frameworks))
    if flash := st.session_state.pop("flash", None):
        st.success(flash)
    if st.button("Onboard an application", type="primary"):
        st.session_state.page = "onboard"
        st.rerun()
    if st.button("Load sample apps", help="Adds the HR CV Screener and Support Chatbot demo applications."):
        added = install_samples(store, ROOT / "samples", st.session_state.frameworks, st.session_state.user)
        st.session_state.flash = f"Loaded {len(added)} sample app(s)." if added else "Sample apps are already loaded."
        st.rerun()
    apps = store.list_apps()
    if not apps:
        st.info("No applications yet.")
    for app in apps:
        with st.container(border=True):
            st.subheader(app.name)
            q = load_questionnaire(store, app.app_id)
            st.caption(f"Created by {app.created_by or 'unknown'} · {app.created_at}")
            if q:
                st.markdown(f'<p class="muted">{q.purpose}</p>', unsafe_allow_html=True)
            st.caption("Repository: " + (app.repo_url or app.repo_path))
            if q:
                show_tier(app, q)
            if st.button("Open application", key=f"open_{app.app_id}"):
                st.session_state.page = "app"
                st.session_state.app_id = app.app_id
                st.rerun()


def sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="brand">🛡️ Provenix</div>', unsafe_allow_html=True)
        st.caption(f"Signed in as **{st.session_state.user}**")
        if st.session_state.get("framework_confirmed"):
            if st.button("Change framework", use_container_width=True):
                st.session_state.framework_confirmed = False
                st.rerun()
        if st.button("Sign out", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        st.divider()
        st.caption(f"LLM mode: `{settings.llm_mode}`")


if "user" not in st.session_state:
    sign_in()
else:
    sidebar()
    if st.session_state.get("framework_confirmed"):
        if st.session_state.get("page") == "onboard":
            onboarding.render(store)
        elif st.session_state.get("page") == "app":
            app_page.render(store, settings, st.session_state.app_id)
        else:
            home()
    else:
        framework_picker()
