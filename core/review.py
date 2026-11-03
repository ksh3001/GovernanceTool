"""Human review: confirm or override each finding. The tool's own finding is never changed."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .findings import STATUS_LABELS, Finding, FindingsFile, Status, now


class ReviewDecision(BaseModel):
    control_id: str
    decision: Literal["confirmed", "overridden"]
    tool_status: Status
    final_status: Status
    note: str = ""
    reviewer: str
    run: str  # finished_at of the assessment run this decision belongs to
    at: str = Field(default_factory=now)


class ReviewFile(BaseModel):
    app_id: str
    framework: str
    decisions: dict[str, ReviewDecision] = Field(default_factory=dict)  # latest decision per control
    history: list[ReviewDecision] = Field(default_factory=list)  # every decision, oldest first (audit trail)


def review_path(framework: str) -> str:
    return f"review/{framework}.json"


def record_decision(review: ReviewFile, finding: Finding, *, decision: str, final_status: str | None,
                    note: str, reviewer: str, run: str) -> ReviewDecision:
    """Validate and record a decision. Raises ValueError with a message safe to show."""
    note = note.strip()
    if not reviewer.strip():
        raise ValueError("A reviewer name is required.")
    if decision == "confirmed":
        final = finding.status
    elif decision == "overridden":
        if final_status not in STATUS_LABELS:
            raise ValueError("Choose the status you are overriding to.")
        if final_status == finding.status:
            raise ValueError("The new status is the same as the tool's status. Confirm the finding instead.")
        if not note:
            raise ValueError("A note is required when overriding a finding.")
        final = final_status
    else:
        raise ValueError(f"Unknown decision {decision!r}.")
    entry = ReviewDecision(control_id=finding.control_id, decision=decision, tool_status=finding.status,
                           final_status=final, note=note, reviewer=reviewer.strip(), run=run)
    review.decisions[finding.control_id] = entry
    review.history.append(entry)
    return entry


def current_decisions(review: ReviewFile | None, findings: FindingsFile) -> dict[str, ReviewDecision]:
    """Decisions that belong to this run. Decisions from an earlier run are not applied."""
    if review is None:
        return {}
    return {cid: d for cid, d in review.decisions.items() if d.run == findings.finished_at}


def stale_count(review: ReviewFile | None, findings: FindingsFile) -> int:
    return 0 if review is None else len(review.decisions) - len(current_decisions(review, findings))


def final_status(finding: Finding, decisions: dict[str, ReviewDecision]) -> str:
    d = decisions.get(finding.control_id)
    return d.final_status if d else finding.status
