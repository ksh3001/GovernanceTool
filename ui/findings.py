"""Shared finding display helpers."""
from __future__ import annotations

from core.findings import STATUS_LABELS, Finding

STATUS_COLOURS = {"met": "#15803D", "partial": "#A16207", "not_met": "#B91C1C",
                  "insufficient_evidence": "#475569", "not_applicable": "#94A3B8"}


def badge(status: str) -> str:
    return (f'<span class="tag" style="background:{STATUS_COLOURS[status]};color:#fff">'
            f'{STATUS_LABELS[status]}</span>')


def verification_text(f: Finding) -> str:
    if f.verification == "verified":
        return "✓ Verified: a second check confirmed the cited evidence supports this rating." + (
            f" {f.verifier_note}" if f.verifier_note else "")
    if f.verification == "failed":
        was = f" (was {STATUS_LABELS[f.model_status].lower()})" if f.model_status else ""
        return f"✗ Failed verification: shown as insufficient evidence{was}." + (
            f" {f.verifier_note}" if f.verifier_note else "")
    if f.verification == "unverified":
        return "? Not verified: the second check could not run. Treat this rating with caution."
    return ""
