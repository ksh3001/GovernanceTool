"""Finding models, saved per application and per framework as findings/<framework>.json."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["met", "partial", "not_met", "insufficient_evidence", "not_applicable"]
STATUS_LABELS = {
    "met": "Met", "partial": "Partial", "not_met": "Not met",
    "insufficient_evidence": "Insufficient evidence", "not_applicable": "Not applicable",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Citation(BaseModel):
    """Evidence made by code: the model only names a file and line range."""
    area: str
    path: str
    start: int
    end: int
    excerpt: str  # copied from the file by code, never written by the model
    excerpt_sha256: str
    file_sha256: str
    role: Literal["supports", "contradicted_claim"] = "supports"

    @property
    def ref(self) -> str:
        return f"{self.area}/{self.path}:{self.start}-{self.end}"


class FileConsidered(BaseModel):
    key: str
    score: float
    full: bool


class Finding(BaseModel):
    control_id: str
    article: str
    title: str
    status: Status
    rationale: str = ""  # the model's reasoning, shown as reasoning and not as evidence
    citations: list[Citation] = Field(default_factory=list)
    coverage: Literal["complete", "partial", "n/a"] = "complete"
    files_considered: list[FileConsidered] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)  # e.g. why a status was downgraded
    model_status: Status | None = None  # what the model said, if a guardrail changed it
    source: Literal["model", "rule"] = "model"  # rule = decided by code (not applicable)
    verification: Literal["verified", "failed", "unverified", "skipped"] = "skipped"
    verifier_note: str = ""
    error: str | None = None


class FindingsFile(BaseModel):
    app_id: str
    framework: str
    tier: str = ""
    tier_label: str = ""
    repo_commit: str = ""
    llm_mode: str = ""
    started_at: str = Field(default_factory=now)
    finished_at: str = ""
    findings: list[Finding] = Field(default_factory=list)

    def by_control(self) -> dict[str, Finding]:
        return {f.control_id: f for f in self.findings}


def findings_path(framework: str) -> str:
    return f"findings/{framework}.json"
