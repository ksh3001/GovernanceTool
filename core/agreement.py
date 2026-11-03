"""Agreement score: how often the tool's own status matched the expert answer key.

Only apps with an answer key get a score. Reviewer overrides are not counted here,
because the score measures the tool, not the tool plus its reviewer.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from .answer_key import AnswerKey, KeyEvidence
from .findings import Citation, FindingsFile


class ControlAgreement(BaseModel):
    control_id: str
    article: str
    title: str
    tool_status: str
    expert_status: str
    match: bool
    rule_decided: bool  # not applicable, decided by code and not by the model
    evidence_match: bool | None = None  # None when the expert lists no evidence
    expert_note: str = ""


class TrapResult(BaseModel):
    control_id: str
    description: str
    detected: bool  # the tool cited the document claim as not backed by the code


class Agreement(BaseModel):
    key_status: str
    reviewed_by: str | None = None
    tier_tool: str
    tier_expert: str
    tier_match: bool
    controls: list[ControlAgreement] = Field(default_factory=list)
    traps: list[TrapResult] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.controls)

    @property
    def agreed(self) -> int:
        return sum(c.match for c in self.controls)

    @property
    def assessed(self) -> list[ControlAgreement]:
        """Controls the model had to judge (not decided by rule)."""
        return [c for c in self.controls if not c.rule_decided]

    @property
    def assessed_total(self) -> int:
        return len(self.assessed)

    @property
    def assessed_agreed(self) -> int:
        return sum(c.match for c in self.assessed)

    @property
    def confirmed_by_expert(self) -> bool:
        return self.key_status != "draft_unreviewed" and bool(self.reviewed_by)


def _name(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).name


def _overlaps(c: Citation, e: KeyEvidence) -> bool:
    """Same file (by name, so docs/x.md matches x.md) and overlapping line ranges."""
    return _name(c.path) == _name(e.file) and c.start <= e.lines[1] and e.lines[0] <= c.end


def compute_agreement(findings: FindingsFile, key: AnswerKey, tool_tier: str) -> Agreement:
    out = Agreement(key_status=key.status, reviewed_by=key.reviewed_by, tier_tool=tool_tier,
                    tier_expert=key.expected_tier, tier_match=tool_tier == key.expected_tier)
    for f in findings.findings:
        expert = key.controls.get(f.control_id)
        if expert is None:
            continue  # the key does not cover this control, so it cannot be scored
        wanted = [e for e in expert.evidence if e.role == "supports"]
        ev = None
        if wanted:
            ev = any(_overlaps(c, e) for c in f.citations if c.role == "supports" for e in wanted)
        out.controls.append(ControlAgreement(
            control_id=f.control_id, article=f.article, title=f.title, tool_status=f.status,
            expert_status=expert.status, match=f.status == expert.status, rule_decided=f.source == "rule",
            evidence_match=ev, expert_note=expert.note))
    by_id = findings.by_control()
    for trap in key.trap_cases:
        claim_files = {_name(e.file) for e in key.controls[trap.control].evidence if e.role == "contradicted_claim"}
        finding = by_id.get(trap.control)
        detected = bool(finding) and any(c.role == "contradicted_claim" and _name(c.path) in claim_files
                                         for c in finding.citations)
        out.traps.append(TrapResult(control_id=trap.control, description=trap.description, detected=detected))
    return out
