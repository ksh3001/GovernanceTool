"""Run section: what will be read, what it may cost, and the button that starts the assessment."""
from __future__ import annotations

import streamlit as st

from core.assess import run_assessment
from core.config import Settings
from core.controls import Control
from core.findings import findings_path
from core.ingest import IngestResult
from core.llm import LLMClient
from core.models import AppRecord
from core.questionnaire import Questionnaire
from core.runplan import RunPlan, build_run_plan
from core.store import Store
from core.tiers import Applicability, TierResult


def render_run(store: Store, settings: Settings, app: AppRecord, framework: str, controls: list[Control],
               applic: list[Applicability], q: Questionnaire, tier: TierResult | None, ingested: IngestResult,
               has_findings: bool) -> RunPlan:
    plan = build_run_plan(ingested, controls, applic)

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

    label = "Run assessment again" if has_findings else "Start assessment"
    if has_findings:
        st.caption("Running again replaces the findings. Review decisions made on the earlier run are kept "
                   "in the audit trail but are not applied to the new findings.")
    if st.button(label, type="primary", key=f"start_{framework}"):
        bar = st.progress(0.0, text="Starting…")
        try:
            result = run_assessment(
                app_id=app.app_id, framework=framework, controls=controls, applicability=applic, q=q, tier=tier,
                ingested=ingested, llm=LLMClient(settings), repo_commit=app.repo_commit,
                progress=lambda done, total, text: bar.progress(done / max(total, 1), text=text),
                log=lambda entry: store.append_log(app.app_id, f"logs/run_{framework}.jsonl", entry))
        except RuntimeError as exc:  # configuration or replay problem: nothing is saved
            bar.empty()
            st.error(str(exc))
        else:
            store.save(app.app_id, findings_path(framework), result)
            st.session_state.goto_section = (framework, "Dashboard")
            st.rerun()

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
    return plan
