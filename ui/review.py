"""Review screen: read each finding, check its evidence, then confirm or override it."""
from __future__ import annotations

import streamlit as st

from core.findings import STATUS_LABELS, FindingsFile
from core.ingest import IngestResult
from core.review import ReviewFile, current_decisions, final_status, record_decision, review_path, stale_count
from core.store import Store
from ui import citation
from ui.findings import badge, verification_text

FILTERS = ["All", "Needs review", "Gaps (not met / insufficient)", "Overridden"]


def render(store: Store, app_id: str, framework: str, findings: FindingsFile, review: ReviewFile | None,
           ingested: IngestResult) -> None:
    review = review or ReviewFile(app_id=app_id, framework=framework)
    decisions = current_decisions(review, findings)
    files = ingested.by_key()
    user = st.session_state.user

    if findings.llm_mode == "fake":
        st.warning("These findings came from the placeholder (fake) model. Reviewing them is only a rehearsal.")
    if (n := stale_count(review, findings)):
        st.info(f"{n} earlier decision(s) belong to a previous assessment run and are not applied to these findings.")

    done = len(decisions)
    reviewable = [f for f in findings.findings]
    st.progress(done / max(len(reviewable), 1), text=f"{done} of {len(reviewable)} findings reviewed by you or your team")
    choice = st.radio("Show", FILTERS, horizontal=True, key=f"filter_{framework}")
    focus = st.session_state.pop("focus_control", None)

    def visible(f) -> bool:
        if choice == "Needs review":
            return f.control_id not in decisions and f.status != "not_applicable"
        if choice.startswith("Gaps"):
            return final_status(f, decisions) in ("not_met", "insufficient_evidence")
        if choice == "Overridden":
            return f.control_id in decisions and decisions[f.control_id].decision == "overridden"
        return True

    shown = [f for f in findings.findings if visible(f)]
    if not shown:
        st.info("Nothing matches this filter.")
    for f in shown:
        d = decisions.get(f.control_id)
        final = final_status(f, decisions)
        title = f"{f.article} · {f.title}"
        with st.container(border=True):
            head = badge(f.status)
            if d and d.final_status != f.status:
                head += f' → reviewer: {badge(d.final_status)}'
            elif d:
                head += ' <span class="tag tag-ok">Confirmed</span>'
            st.markdown(f"{head} **{title}**", unsafe_allow_html=True)
            with st.expander("Open finding", expanded=(focus == f.control_id)):
                if f.rationale:
                    st.write(f.rationale)
                if (vt := verification_text(f)):
                    st.caption(vt)
                for flag in f.flags:
                    st.caption(f"⚠ {flag}")
                if f.error:
                    st.caption(f"Error: {f.error}")
                if f.coverage == "partial":
                    st.caption("Coverage was limited: some relevant files were trimmed or left out.")
                for c in f.citations:
                    citation.render(c, files.get(f"{c.area}:{c.path}"))
                if f.files_considered:
                    st.caption("Files considered: " + ", ".join(
                        f"{x.key.split(':', 1)[1]} ({x.score:g}{'' if x.full else ', trimmed'})" for x in f.files_considered))
                if d:
                    st.caption(f"{d.decision.capitalize()} by {d.reviewer} · {d.at}" + (f" · “{d.note}”" if d.note else ""))
                _decision_form(store, review, f, findings, user, framework, app_id, d is not None)


def _decision_form(store, review, finding, findings, user, framework, app_id, has_decision) -> None:
    with st.form(f"decide_{framework}_{finding.control_id}"):
        action = st.radio("Your decision", ["Confirm the tool's finding", "Override"], horizontal=True,
                          key=f"act_{framework}_{finding.control_id}")
        options = [s for s in STATUS_LABELS if s != finding.status]
        new_status = st.selectbox("Override to", options, format_func=STATUS_LABELS.get,
                                  key=f"new_{framework}_{finding.control_id}",
                                  help="Only used when you choose Override.")
        note = st.text_area("Note (required for an override)", key=f"note_{framework}_{finding.control_id}")
        submitted = st.form_submit_button("Update decision" if has_decision else "Save decision", type="primary",
                                          key=f"save_{framework}_{finding.control_id}")
    if submitted:
        overriding = action == "Override"
        try:
            record_decision(review, finding, decision="overridden" if overriding else "confirmed",
                            final_status=new_status if overriding else None, note=note, reviewer=user,
                            run=findings.finished_at)
        except ValueError as exc:
            st.error(str(exc))
            return
        store.save(app_id, review_path(framework), review)
        st.session_state.focus_control = finding.control_id
        st.rerun()
