"""Pre-run summary: what will be read, what was skipped, what it may cost, and coverage."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .controls import Control
from .ingest import IngestResult, SkippedFile
from .relevance import DEFAULT_BUDGET_TOKENS, Selection, select_files
from .tiers import Applicability

PROMPT_OVERHEAD_TOKENS = 700  # instructions, control text and the answer, per control


class ControlPlan(BaseModel):
    control_id: str
    article: str
    title: str
    applies: bool
    not_applicable_reason: str = ""
    selection: Selection | None = None


class RunPlan(BaseModel):
    files_found: int
    files_used: int
    files_skipped: list[SkippedFile] = Field(default_factory=list)
    unreadable: list[SkippedFile] = Field(default_factory=list)
    controls: list[ControlPlan]
    estimated_tokens: int
    partial_controls: list[str] = Field(default_factory=list)

    @property
    def coverage(self) -> str:
        return "partial" if self.partial_controls else "complete"


def build_run_plan(ingested: IngestResult, controls: list[Control], applicability: list[Applicability],
                   budget_tokens: int = DEFAULT_BUDGET_TOKENS) -> RunPlan:
    applies = {a.control_id: a for a in applicability}
    plans, used, tokens, partial = [], set(), 0, []
    for c in controls:
        a = applies[c.id]
        if not a.applies:
            plans.append(ControlPlan(control_id=c.id, article=c.article, title=c.title, applies=False,
                                     not_applicable_reason=a.reason))
            continue
        sel = select_files(ingested, c, budget_tokens)
        used.update(f.key for f in sel.files)
        tokens += sel.tokens + PROMPT_OVERHEAD_TOKENS
        if sel.coverage == "partial":
            partial.append(c.id)
        plans.append(ControlPlan(control_id=c.id, article=c.article, title=c.title, applies=True, selection=sel))
    return RunPlan(files_found=len(ingested.files), files_used=len(used), files_skipped=ingested.skipped,
                   unreadable=ingested.unreadable, controls=plans, estimated_tokens=tokens, partial_controls=partial)
