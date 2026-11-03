"""Application page: the run summary shown before an assessment starts."""
from __future__ import annotations

import streamlit as st

from core.config import Settings
from core.controls import load_controls
from core.ingest import ingest
from core.onboarding import load_questionnaire
from core.runplan import build_run_plan
from core.store import Store
from core.tiers import control_applicability, load_classifier


def render(store: Store, settings: Settings, app_id: str) -> None:
    app = store.get_app(app_id)
    if app is None:
        st.error("Application not found.")
        return
    if st.button("← Back to applications"):
        st.session_state.page = "home"
        st.rerun()
    st.title(app.name)
    q = load_questionnaire(store, app_id)
    if q is None:
        st.error("This application has no questionnaire.")
        return

    for fw in app.frameworks:
        pack_dir = settings.packs_dir / fw
        classify = load_classifier(pack_dir)
        tier = classify(q) if classify else None
        controls = load_controls(pack_dir)
        applic = control_applicability(controls, tier.tier if tier else "high", q)
        ingested = ingest(app.repo_path, app.docs_path or None)
        plan = build_run_plan(ingested, controls, applic)

        st.header(fw.replace("_", " ").upper() if fw != "eu_ai_act" else "EU AI Act")
        if tier:
            st.markdown(f"**{tier.label}** · {tier.legal_basis}")
            st.caption(tier.reason)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Files found", plan.files_found)
        c2.metric("Files used", plan.files_used)
        c3.metric("Skipped", len(plan.files_skipped))
        c4.metric("Est. tokens", f"{plan.estimated_tokens:,}")

        if plan.coverage == "partial":
            names = ", ".join(c.article for c in plan.controls if c.control_id in plan.partial_controls)
            st.warning(f"Partial coverage for {names}: some relevant files were trimmed or left out. "
                       "These controls cannot be rated 'not met'; they will show 'insufficient evidence' instead.")
        else:
            st.success("Full coverage: every relevant file will be read in full.")
        if plan.unreadable:
            st.warning("Could not read: " + "; ".join(f"{u.path} ({u.reason})" for u in plan.unreadable))

        st.subheader("Controls")
        for c in plan.controls:
            with st.container(border=True):
                st.markdown(f"**{c.article}** · {c.title}")
                if not c.applies:
                    st.caption(f"Not applicable. {c.not_applicable_reason}")
                    continue
                sel = c.selection
                note = "whole app fits in the budget" if sel.shortcut else (
                    f"{len(sel.trimmed)} trimmed, {len(sel.left_out)} left out" if sel.trimmed or sel.left_out
                    else "all relevant files in full")
                st.caption(f"{len(sel.files)} files · {sel.tokens:,} tokens · {note}")
                with st.expander("Files considered"):
                    for f in sel.files:
                        span = "full file" if f.full else "lines " + ", ".join(f"{s.start}-{s.end}" for s in f.segments)
                        st.markdown(f"`{f.area}/{f.path}` · score {f.score:g} · {span}")

        with st.expander(f"Skipped files ({len(plan.files_skipped)})"):
            for s in plan.files_skipped:
                st.markdown(f"`{s.area}/{s.path}` — {s.reason}")

        st.button("Start assessment", type="primary", disabled=True, key=f"start_{fw}",
                  help="The assessment loop is built in the next step.")
