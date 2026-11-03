"""Compliance score and counts. The score is our own internal metric, not an official EU measure."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .findings import STATUS_LABELS, Finding, FindingsFile
from .review import ReviewDecision, current_decisions, final_status, ReviewFile

GAP_ORDER = ("not_met", "insufficient_evidence")


def compliance_score(statuses: list[str]) -> float | None:
    """(met + 0.5 x partial) / applicable controls. Not applicable controls are left out.
    Returns None when nothing is applicable."""
    applicable = [s for s in statuses if s != "not_applicable"]
    if not applicable:
        return None
    return (applicable.count("met") + 0.5 * applicable.count("partial")) / len(applicable)


class Gap(BaseModel):
    control_id: str
    article: str
    title: str
    status: str
    rationale: str = ""


class Summary(BaseModel):
    counts: dict[str, int]  # final status -> count
    applicable: int
    score: float | None  # from final statuses (reviewer's where overridden)
    tool_score: float | None  # from the tool's statuses only
    reviewed: int  # findings with a decision for this run
    overridden: int
    stale_decisions: int  # decisions from an earlier run, not applied
    gaps: list[Gap] = Field(default_factory=list)


def summarise(findings: FindingsFile, review: ReviewFile | None) -> Summary:
    decisions: dict[str, ReviewDecision] = current_decisions(review, findings)
    finals = {f.control_id: final_status(f, decisions) for f in findings.findings}
    counts = {s: sum(v == s for v in finals.values()) for s in STATUS_LABELS}
    gaps = [Gap(control_id=f.control_id, article=f.article, title=f.title, status=finals[f.control_id],
                rationale=(decisions[f.control_id].note if f.control_id in decisions and decisions[f.control_id].note
                           else f.rationale))
            for status in GAP_ORDER for f in findings.findings if finals[f.control_id] == status]
    return Summary(
        counts=counts, applicable=sum(v != "not_applicable" for v in finals.values()),
        score=compliance_score(list(finals.values())),
        tool_score=compliance_score([f.status for f in findings.findings]),
        reviewed=len(decisions), overridden=sum(d.decision == "overridden" for d in decisions.values()),
        stale_decisions=(len(review.decisions) - len(decisions)) if review else 0, gaps=gaps)
