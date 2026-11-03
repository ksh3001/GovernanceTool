"""Citation viewer: the cited lines highlighted inside a few lines of surrounding file context."""
from __future__ import annotations

import html

import streamlit as st

from core.findings import Citation
from core.ingest import IngestedFile

CONTEXT = 3


def _rows(lines: list[tuple[int, str]], cited: range, css: str) -> str:
    out = []
    for n, text in lines:
        cls = css if n in cited else ""
        out.append(f'<div class="row {cls}"><div class="n">{n}</div><div class="t">{html.escape(text) or "&nbsp;"}</div></div>')
    return '<div class="cv">' + "".join(out) + "</div>"


def render(c: Citation, source: IngestedFile | None) -> None:
    claim = c.role == "contradicted_claim"
    st.markdown(f"**{'Document claim not backed by the code' if claim else 'Evidence'}** · `{html.escape(c.ref)}`")
    cited = range(c.start, c.end + 1)
    if source is not None and source.sha256 == c.file_sha256:
        lines = source.text.splitlines()
        lo, hi = max(1, c.start - CONTEXT), min(len(lines), c.end + CONTEXT)
        shown = [(n, lines[n - 1]) for n in range(lo, hi + 1)]
    else:
        if source is not None:
            st.warning("This file has changed since the assessment, so only the saved excerpt is shown.")
        shown = list(enumerate(c.excerpt.splitlines(), c.start))
    st.markdown(_rows(shown, cited, "claim" if claim else "hit"), unsafe_allow_html=True)
    st.caption(f"Excerpt copied by the tool, not written by the model · sha256 {c.excerpt_sha256[:12]}")
