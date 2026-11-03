"""Expert answer keys for the sample apps (used for the agreement score)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Status = Literal["met", "partial", "not_met", "insufficient_evidence", "not_applicable"]


class KeyEvidence(BaseModel):
    area: Literal["repo", "docs"]
    file: str
    lines: tuple[int, int]
    contains: str
    role: Literal["supports", "contradicted_claim"] = "supports"


class KeyControl(BaseModel):
    status: Status
    note: str = ""
    evidence: list[KeyEvidence] = Field(default_factory=list)


class TrapCase(BaseModel):
    control: str
    description: str


class AnswerKey(BaseModel):
    app_name: str
    repo_url: str | None = None  # public sample repo, used to match URL-onboarded apps to their key
    framework: str
    expected_tier: str
    tier_rule: str
    status: str = "draft_unreviewed"
    reviewed_by: str | None = None
    controls: dict[str, KeyControl]
    trap_cases: list[TrapCase] = Field(default_factory=list)


def load_answer_key(path: Path) -> AnswerKey:
    return AnswerKey(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def find_answer_key(samples_dir: Path, repo_url: str) -> Path | None:
    """Path of the answer key whose repo_url matches, or None (apps without a key get no agreement score)."""
    from .fetch import normalize_url
    wanted = normalize_url(repo_url)
    for path in sorted(Path(samples_dir).glob("*/answer_key.yaml")):
        key = load_answer_key(path)
        if key.repo_url and normalize_url(key.repo_url) == wanted:
            return path.resolve()
    return None
