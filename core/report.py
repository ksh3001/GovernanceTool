"""Standalone HTML report. Save as PDF with the browser's Print command."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .agreement import Agreement
from .findings import STATUS_LABELS, FindingsFile
from .models import AppRecord, PackInfo
from .review import ReviewFile, current_decisions
from .scoring import summarise
from .tiers import TierResult

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                   autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def build_report_html(*, app: AppRecord, pack: PackInfo, tier: TierResult | None, findings: FindingsFile,
                      review: ReviewFile | None, agreement: Agreement | None, coverage_partial: bool) -> str:
    summary = summarise(findings, review)
    decisions = current_decisions(review, findings)
    top = max(max(summary.counts.values()), 1)
    bars = [{"key": k, "label": STATUS_LABELS[k], "count": n, "pct": round(100 * n / top)} for k, n in summary.counts.items()]
    return _env.get_template("report.html").render(
        app=app, pack=pack, tier=tier, findings=findings, summary=summary, decisions=decisions,
        agreement=agreement, labels=STATUS_LABELS, bars=bars, coverage_partial=coverage_partial,
        score_text=_pct(summary.score), tool_score_text=_pct(summary.tool_score),
        reviewer_names=sorted({d.reviewer for d in decisions.values()}),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))


def report_filename(app: AppRecord, framework: str) -> str:
    return f"provenix-{app.app_id}-{framework}-report.html"
