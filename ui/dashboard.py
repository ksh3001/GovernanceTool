"""Dashboard for one application and one framework."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from core.agreement import Agreement
from core.findings import STATUS_LABELS, FindingsFile
from core.review import ReviewFile
from core.scoring import summarise
from core.tiers import TierResult
from ui.findings import STATUS_COLOURS, badge

TIER_COLOURS = {"prohibited": "#B91C1C", "high": "#C2410C", "limited": "#A16207",
                "minimal": "#15803D", "out_of_scope": "#475569"}


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def _go_review(framework: str, control_id: str) -> None:
    st.session_state[f"section_{framework}"] = "Review"
    st.session_state.focus_control = control_id


def render(framework: str, tier: TierResult | None, findings: FindingsFile, review: ReviewFile | None,
           coverage_partial: bool, agreement: Agreement | None = None) -> None:
    s = summarise(findings, review)
    left, mid, right = st.columns([1.3, 1, 1])
    with left:
        st.caption("Risk tier")
        if tier:
            colour = TIER_COLOURS.get(tier.tier, "#475569")
            st.markdown(f'<span class="tag" style="background:{colour};color:#fff;font-size:1rem;padding:4px 14px">'
                        f'{tier.label}</span>', unsafe_allow_html=True)
            st.caption(f"{tier.legal_basis} · rule `{tier.rule_id}`")
            st.write(tier.reason)
        else:
            st.write("This framework has no risk tiers.")
    mid.metric("Compliance score", _pct(s.score),
               delta=None if s.score == s.tool_score else f"tool alone: {_pct(s.tool_score)}", delta_color="off",
               help="(met + 0.5 × partial) ÷ applicable controls. Uses your decisions where you overrode a finding.")
    right.metric("Reviewed", f"{s.reviewed} of {len(findings.findings)}", delta=f"{s.overridden} overridden",
                 delta_color="off")
    st.caption("The compliance score is Provenix's own internal metric. It is not an official EU rating. "
               "'Not met' and 'insufficient evidence' count as 0, and 'not applicable' controls are left out.")
    if s.stale_decisions:
        st.info(f"{s.stale_decisions} review decision(s) from an earlier run are not applied.")
    if findings.llm_mode == "fake":
        st.warning("Placeholder (fake) model results: the numbers below are not real findings.")

    st.subheader("Controls by status")
    df = pd.DataFrame({"Status": [STATUS_LABELS[k] for k in STATUS_LABELS], "Controls": list(s.counts.values())})
    chart = alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Status:N", sort=list(df["Status"]), title=None),
        x=alt.X("Controls:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Status:N", legend=None, scale=alt.Scale(
            domain=[STATUS_LABELS[k] for k in STATUS_LABELS], range=[STATUS_COLOURS[k] for k in STATUS_LABELS])),
        tooltip=["Status", "Controls"]).properties(height=190)
    st.altair_chart(chart, width="stretch")

    st.subheader("Top gaps")
    if not s.gaps:
        st.success("No gaps: every applicable control is met or partial.")
    for g in s.gaps:
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{badge(g.status)} **{g.article}** · {g.title}", unsafe_allow_html=True)
            if g.rationale:
                c1.caption(g.rationale[:240] + ("…" if len(g.rationale) > 240 else ""))
            c2.button("Open", key=f"gap_{framework}_{g.control_id}", on_click=_go_review, args=(framework, g.control_id))

    _agreement(agreement)

    note = "Coverage: some relevant files were trimmed or left out for at least one control. " if coverage_partial \
        else "Coverage: every relevant file was read in full. "
    st.caption(note + "Evidence is found by keyword search, which can miss files with unusual names. "
                      f"Run finished {findings.finished_at} · mode {findings.llm_mode}"
               + (f" · commit {findings.repo_commit[:10]}" if findings.repo_commit else ""))


def _agreement(a: Agreement | None) -> None:
    st.subheader("Agreement with the expert")
    if a is None:
        st.caption("No expert answer key exists for this application, so there is no agreement score.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Controls matched", f"{a.assessed_agreed} of {a.assessed_total}",
              help="Controls the model had to judge. The tool's own rating is compared with the expert key, before any reviewer changes.")
    c2.metric("Including rule-decided", f"{a.agreed} of {a.total}")
    c3.metric("Risk tier", "Match" if a.tier_match else "Mismatch", delta=f"tool {a.tier_tool} · expert {a.tier_expert}",
              delta_color="off")
    if not a.confirmed_by_expert:
        st.warning("Draft answer key: the expected results were written by the build team and are not yet confirmed "
                   "by a compliance expert. Do not quote this as validated accuracy.")
    for t in a.traps:
        (st.success if t.detected else st.error)(
            f"Trap case ({t.control_id}): {'detected' if t.detected else 'not detected'}. {t.description}")
    with st.expander("Control by control"):
        for c in a.controls:
            extra = "" if c.evidence_match is None else (" · cited the expected evidence" if c.evidence_match
                                                          else " · did not cite the expected evidence")
            st.markdown(f"{'✅' if c.match else '❌'} **{c.article}** · {c.title} — tool "
                        f"{STATUS_LABELS[c.tool_status].lower()}, expert {STATUS_LABELS[c.expert_status].lower()}{extra}")
