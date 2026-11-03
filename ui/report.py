"""Report section: preview and download the HTML report."""
from __future__ import annotations

import streamlit.components.v1 as components
import streamlit as st

from core.agreement import Agreement
from core.findings import FindingsFile
from core.models import AppRecord, PackInfo
from core.report import build_report_html, report_filename
from core.review import ReviewFile
from core.tiers import TierResult


def render(app: AppRecord, pack: PackInfo, tier: TierResult | None, findings: FindingsFile,
           review: ReviewFile | None, agreement: Agreement | None, coverage_partial: bool) -> None:
    html = build_report_html(app=app, pack=pack, tier=tier, findings=findings, review=review,
                             agreement=agreement, coverage_partial=coverage_partial)
    c1, c2 = st.columns([1, 3])
    c1.download_button("Download report (HTML)", data=html, file_name=report_filename(app, pack.id),
                       mime="text/html", type="primary", key=f"dl_{pack.id}")
    c2.caption("Open the file in a browser and use Print → Save as PDF for a PDF copy. "
               "The report includes your review decisions as they stand now.")
    components.html(html, height=900, scrolling=True)
