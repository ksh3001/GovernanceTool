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
from core.scope import ScopeFile, effective_scope, new_scope, scope_path, scoped_rules
from core.scoring import summarise
from core.runplan import build_run_plan
from core.store import Store
from core.tiers import control_applicability, load_classifier
from ui.nav import header, hint
from ui import dashboard, report as report_view, review as review_view, run_summary, scope as scope_view

SECTIONS = ["Scope", "Run", "Review", "Dashboard", "Report"]  # the order a user works through them


def _step_labels(findings: FindingsFile | None, review: ReviewFile | None, scope: ScopeFile) -> dict[str, str]:
    """Sidebar text for each step, with a marker for progress so the user can see where they are."""
    labels = {"Scope": "1 · Rule scope", "Run": "2 · Run assessment", "Review": "3 · Review findings",
              "Dashboard": "4 · Dashboard", "Report": "5 · Report"}
    if scope.finalised:
        labels["Scope"] += "  ✓"
    if findings is None:
        for s in ("Review", "Dashboard", "Report"):
            labels[s] += "  (run first)"
        return labels
    summary = summarise(findings, review)
    labels["Run"] += "  ✓"
    labels["Review"] += f"  ({summary.reviewed}/{len(findings.reviewable)})"
    return labels


def _next_step(findings: FindingsFile | None, review: ReviewFile | None, scope: ScopeFile) -> str | None:
    if findings is None:
        if not scope.finalised:
            return ("<b>Next step:</b> check the rules the questionnaire selected, adjust them if needed, "
                    "and finalise the scope (step 1).")
        return "<b>Next step:</b> run the assessment on the finalised scope (step 2)."
    left = len(findings.reviewable) - summarise(findings, review).reviewed
    if left:
        return (f"<b>Next step:</b> confirm or override the {left} finding{'s' if left != 1 else ''} still "
                "waiting for a decision (step 3), then download the report (step 5).")
    return "<b>Next step:</b> every finding has a decision. Download the report (step 5)."


def render(store: Store, settings: Settings, app_id: str) -> None:
    app = store.get_app(app_id)
    if app is None:
        st.error("Application not found.")
        return
    q = load_questionnaire(store, app_id)
    if q is None:
        st.error("This application has no questionnaire.")
        return
    if not app.frameworks:
        st.warning("This application has no framework selected.")
        return

    packs = {p.id: p for p in discover_packs(settings.packs_dir)}
    key_path = Path(app.answer_key_path) if app.answer_key_path else None
    answer_key = load_answer_key(key_path) if key_path and key_path.is_file() else None
    goto = st.session_state.pop("goto_section", None)
    if st.session_state.get("_last_app") != app_id:  # a different app starts on its own default step
        for f in app.frameworks:
            st.session_state.pop(f"section_{f}", None)
        st.session_state["_last_app"] = app_id

    fw = app.frameworks[0]
    fw_key = f"fwsel_{app_id}"
    if goto and goto[0] in app.frameworks:
        st.session_state[fw_key] = goto[0]
    if len(app.frameworks) > 1:
        with st.sidebar:
            st.markdown('<div class="navlabel">Framework</div>', unsafe_allow_html=True)
            fw = st.selectbox("Framework", app.frameworks, key=fw_key, label_visibility="collapsed",
                              format_func=lambda f: packs[f].name if f in packs else f)

    pack_dir = settings.packs_dir / fw
    classify = load_classifier(pack_dir)
    tier = classify(q) if classify else None
    pack_controls = load_controls(pack_dir)
    proposed = control_applicability(pack_controls, tier.tier if tier else "high", q)
    scope = store.load(app_id, scope_path(fw), ScopeFile) or new_scope(app_id, fw)
    controls, applic = effective_scope(pack_controls, proposed, scope)
    findings = store.load(app_id, findings_path(fw), FindingsFile)
    review = store.load(app_id, review_path(fw), ReviewFile)
    fw_name = packs[fw].name if fw in packs else fw

    key = f"section_{fw}"
    if goto and goto[0] == fw:
        st.session_state[key] = goto[1]
    if key not in st.session_state:
        st.session_state[key] = "Dashboard" if findings else ("Run" if scope.finalised else "Scope")
    with st.sidebar:
        st.markdown('<div class="navlabel">This application</div>', unsafe_allow_html=True)
        st.markdown(f"**{app.name}**")
        labels = _step_labels(findings, review, scope)
        section = st.radio("Steps", SECTIONS, key=key, format_func=labels.get, label_visibility="collapsed")

    header("Applications", app.name, fw_name, section, mode=settings.llm_mode)
    if flash := st.session_state.pop("flash", None):
        st.success(flash)
    st.title(app.name)
    st.caption(f"Source: {app.repo_url} · commit `{app.repo_commit[:10]}`" if app.repo_url
               else f"Source: local folder {app.repo_path}")
    if message := _next_step(findings, review, scope):
        hint(message)
    if findings and findings.scope_finalised_at and findings.scope_finalised_at != scope.finalised_at:
        st.warning("The rule scope has changed since this assessment ran. Run the assessment again (step 2) so the "
                   "findings match the current scope.")

    if section == "Scope":
        scope_view.render(store, app_id, fw, q, tier, pack_controls, proposed, scope)
        return
    ingested = ingest(app.repo_path, app.docs_path or None)

    if section == "Run":
        run_summary.render_run(store, settings, app, fw, controls, applic, q, tier, ingested, findings is not None,
                               scope)
    elif findings is None:
        st.info("No assessment has been run yet. Open step 1, Run assessment, to start one.")
    else:
        agreement = (compute_agreement(findings, answer_key, tier.tier if tier else "")
                     if answer_key and answer_key.framework == fw else None)
        if section == "Review":
            review_view.render(store, app_id, fw, findings, review, ingested)
        else:
            partial = build_run_plan(ingested, controls, applic).coverage == "partial"
            if section == "Dashboard":
                dashboard.render(fw, tier, findings, review, partial, agreement, controls)
            else:
                report_view.render(app, packs[fw], tier, findings, review, agreement, partial, controls,
                                   scoped_rules(pack_controls, proposed, scope), scope)
