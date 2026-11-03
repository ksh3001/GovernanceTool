"""Read-only findings list. The review screen (confirm/override) is built on top of this later."""
from __future__ import annotations

import html

import streamlit as st

from core.findings import STATUS_LABELS, FindingsFile

STATUS_COLOURS = {"met": "#15803D", "partial": "#A16207", "not_met": "#B91C1C",
                  "insufficient_evidence": "#475569", "not_applicable": "#94A3B8"}


def badge(status: str) -> str:
    return (f'<span class="tag" style="background:{STATUS_COLOURS[status]};color:#fff">'
            f'{STATUS_LABELS[status]}</span>')


def render(findings: FindingsFile) -> None:
    counts = {s: sum(f.status == s for f in findings.findings) for s in STATUS_LABELS}
    cols = st.columns(len(STATUS_LABELS))
    for col, (status, label) in zip(cols, STATUS_LABELS.items()):
        col.metric(label, counts[status])
    if findings.llm_mode == "fake":
        st.warning("These results came from the placeholder (fake) model and are not real findings. "
                   "Set PROVENIX_LLM_MODE=live with Azure credentials to assess for real.")
    st.caption(f"Run finished {findings.finished_at} · mode {findings.llm_mode}"
               + (f" · commit {findings.repo_commit[:10]}" if findings.repo_commit else ""))

    for f in findings.findings:
        with st.container(border=True):
            st.markdown(f"{badge(f.status)} **{f.article}** · {f.title}", unsafe_allow_html=True)
            if f.rationale:
                st.write(f.rationale)
            for flag in f.flags:
                st.caption(f"⚠ {flag}")
            if f.error:
                st.caption(f"Error: {f.error}")
            if f.coverage == "partial":
                st.caption("Coverage was limited: some relevant files were trimmed or left out.")
            if f.citations:
                with st.expander(f"Evidence ({len(f.citations)})"):
                    for c in f.citations:
                        role = "Document claim not backed by code" if c.role == "contradicted_claim" else "Evidence"
                        st.markdown(f"**{role}** · `{html.escape(c.ref)}`")
                        st.code(c.excerpt, language=None)
                        st.caption(f"Excerpt copied by the tool · sha256 {c.excerpt_sha256[:12]}")
            if f.files_considered:
                with st.expander("Files considered"):
                    for fc in f.files_considered:
                        st.markdown(f"`{fc.key}` · score {fc.score:g} · {'full file' if fc.full else 'trimmed'}")
