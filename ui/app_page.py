"""Application page: Dashboard, Review and Run sections for each framework."""
from __future__ import annotations

import streamlit as st

from core.config import Settings
from core.controls import load_controls
from core.findings import FindingsFile, findings_path
from core.ingest import ingest
from core.onboarding import load_questionnaire
from core.packs import discover_packs
from core.review import ReviewFile, review_path
from core.runplan import build_run_plan
from core.store import Store
from core.tiers import control_applicability, load_classifier
from ui import dashboard, review as review_view, run_summary

SECTIONS = ["Dashboard", "Review", "Run"]


def render(store: Store, settings: Settings, app_id: str) -> None:
    app = store.get_app(app_id)
    if app is None:
        st.error("Application not found.")
        return
    if st.button("← Back to applications"):
        st.session_state.page = "home"
        st.rerun()
    st.title(app.name)
    st.caption(f"Source: {app.repo_url} · commit `{app.repo_commit[:10]}`" if app.repo_url
               else f"Source: local folder {app.repo_path}")
    q = load_questionnaire(store, app_id)
    if q is None:
        st.error("This application has no questionnaire.")
        return

    names = {p.id: p.name for p in discover_packs(settings.packs_dir)}
    goto = st.session_state.pop("goto_section", None)
    ingested = ingest(app.repo_path, app.docs_path or None)

    for fw in app.frameworks:
        pack_dir = settings.packs_dir / fw
        classify = load_classifier(pack_dir)
        tier = classify(q) if classify else None
        controls = load_controls(pack_dir)
        applic = control_applicability(controls, tier.tier if tier else "high", q)
        findings = store.load(app_id, findings_path(fw), FindingsFile)
        review = store.load(app_id, review_path(fw), ReviewFile)

        st.header(names.get(fw, fw))
        key = f"section_{fw}"
        if goto and goto[0] == fw:
            st.session_state[key] = goto[1]
        if key not in st.session_state or (findings is None and st.session_state[key] != "Run"):
            st.session_state[key] = "Dashboard" if findings else "Run"
        section = st.radio("Section", SECTIONS, horizontal=True, key=key, label_visibility="collapsed")

        if section == "Run":
            run_summary.render_run(store, settings, app, fw, controls, applic, q, tier, ingested, findings is not None)
        elif findings is None:
            st.info("No assessment has been run yet. Open the Run section to start one.")
        elif section == "Dashboard":
            partial = build_run_plan(ingested, controls, applic).coverage == "partial"
            dashboard.render(fw, tier, findings, review, partial)
        else:
            review_view.render(store, app_id, fw, findings, review, ingested)
