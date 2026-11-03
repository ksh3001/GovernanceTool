"""Application page: Dashboard, Review and Run sections for each framework."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.agreement import compute_agreement
from core.answer_key import load_answer_key
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
from ui import dashboard, report as report_view, review as review_view, run_summary

SECTIONS = ["Dashboard", "Review", "Report", "Run"]


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

    packs = {p.id: p for p in discover_packs(settings.packs_dir)}
    key_path = Path(app.answer_key_path) if app.answer_key_path else None
    answer_key = load_answer_key(key_path) if key_path and key_path.is_file() else None
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

        st.header(packs[fw].name if fw in packs else fw)
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
        else:
            agreement = (compute_agreement(findings, answer_key, tier.tier if tier else "")
                         if answer_key and answer_key.framework == fw else None)
            if section == "Review":
                review_view.render(store, app_id, fw, findings, review, ingested)
            else:
                partial = build_run_plan(ingested, controls, applic).coverage == "partial"
                if section == "Dashboard":
                    dashboard.render(fw, tier, findings, review, partial, agreement)
                else:
                    report_view.render(app, packs[fw], tier, findings, review, agreement, partial)
