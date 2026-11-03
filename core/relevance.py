"""File-relevance filter: choose which files (or parts of files) go to the model per control.

Plain keyword scoring, no embeddings. Every choice is recorded so a reviewer can
see what the model was shown, and anything cut sets a coverage flag.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from .controls import Control
from .ingest import IngestedFile, IngestResult

DEFAULT_BUDGET_TOKENS = 12_000
CONTEXT_LINES = 20
MIN_USEFUL_TOKENS = 300  # do not bother including a sliver smaller than this
BASELINE_NAMES = ("readme", "config", "model_card", "model-card", "policy", "settings")

Coverage = Literal["complete", "partial"]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _pattern(term: str) -> re.Pattern:
    # Match at the start of a word-ish run: "log" matches log_decision and logging, not catalog.
    return re.compile(r"(?<![a-z])" + re.escape(term.lower()))


class Segment(BaseModel):
    start: int  # 1-based, inclusive
    end: int
    text: str


class SelectedFile(BaseModel):
    key: str
    area: str
    path: str
    kind: str
    score: float
    full: bool
    segments: list[Segment]
    tokens: int


class Selection(BaseModel):
    control_id: str
    budget_tokens: int
    files: list[SelectedFile] = Field(default_factory=list)
    trimmed: list[str] = Field(default_factory=list)  # keys of files cut down to line windows
    left_out: list[str] = Field(default_factory=list)  # keys of files with a score that did not fit
    scores: dict[str, float] = Field(default_factory=dict)
    shortcut: bool = False  # whole app fit in the budget
    coverage: Coverage = "complete"

    @property
    def tokens(self) -> int:
        return sum(f.tokens for f in self.files)


def score_file(f: IngestedFile, control: Control) -> float:
    path = f.path.lower()
    text = f.text.lower()
    score = 0.0
    for term in control.search_terms:
        pat = _pattern(term)
        if pat.search(path):
            score += 3
        hits = len(pat.findall(text))
        score += min(hits, 5)
    if score == 0:
        # Files with no keyword hit are only candidates if they are baseline context files.
        return 0.5 if any(n in path for n in BASELINE_NAMES) else 0.0
    wanted = control.expected_evidence
    if wanted == "both" or (wanted == "code" and f.kind in ("code", "config")) or (wanted == "document" and f.kind == "doc"):
        score += 2 if wanted != "both" else 1
    return score


def _windows(f: IngestedFile, control: Control, max_tokens: int) -> list[Segment]:
    """Best-matching line windows of one file within max_tokens, original line numbers kept."""
    lines = f.text.splitlines()
    pats = [_pattern(t) for t in control.search_terms]
    hit_lines = [i for i, ln in enumerate(lines) if any(p.search(ln.lower()) for p in pats)]
    if not hit_lines:
        hit_lines = [0]
    # Grow windows around hits and merge overlaps. If nothing fits, tighten the context and retry,
    # so a small budget keeps the lines that matched and not just the top of the file.
    chosen: list[Segment] = []
    for context in (CONTEXT_LINES, 10, 5, 2, 0):
        spans: list[list[int]] = []
        for i in hit_lines:
            lo, hi = max(0, i - context), min(len(lines) - 1, i + context)
            if spans and lo <= spans[-1][1] + 1:
                spans[-1][1] = max(spans[-1][1], hi)
                spans[-1][2] += 1
            else:
                spans.append([lo, hi, 1])
        used = 0
        for lo, hi, hits in sorted(spans, key=lambda s: -s[2] / (s[1] - s[0] + 1)):
            text = "\n".join(lines[lo:hi + 1])
            cost = estimate_tokens(text)
            if used + cost <= max_tokens:
                chosen.append(Segment(start=lo + 1, end=hi + 1, text=text))
                used += cost
        if chosen:
            break
    if not chosen:  # even a single matching line is too big: cut it to fit
        lo, hi, _ = max(spans, key=lambda s: s[2])
        end, size = lo, 0
        while end <= hi and size + estimate_tokens(lines[end]) <= max_tokens:
            size += estimate_tokens(lines[end])
            end += 1
        end = max(end, lo + 1)  # always keep at least one line
        chosen.append(Segment(start=lo + 1, end=end, text="\n".join(lines[lo:end])))
    return sorted(chosen, key=lambda s: s.start)


def _whole(f: IngestedFile, score: float) -> SelectedFile:
    return SelectedFile(key=f.key, area=f.area, path=f.path, kind=f.kind, score=score, full=True,
                        segments=[Segment(start=1, end=max(1, f.lines), text=f.text)], tokens=estimate_tokens(f.text))


def _partial(f: IngestedFile, control: Control, score: float, max_tokens: int) -> SelectedFile:
    segs = _windows(f, control, max_tokens)
    return SelectedFile(key=f.key, area=f.area, path=f.path, kind=f.kind, score=score, full=False,
                        segments=segs, tokens=sum(estimate_tokens(s.text) for s in segs))


def select_files(ingested: IngestResult, control: Control, budget_tokens: int = DEFAULT_BUDGET_TOKENS) -> Selection:
    files = ingested.files
    sel = Selection(control_id=control.id, budget_tokens=budget_tokens)
    sel.scores = {f.key: round(score_file(f, control), 2) for f in files}

    # Small apps: send everything, deterministic and simple.
    if sum(estimate_tokens(f.text) for f in files) <= budget_tokens:
        sel.shortcut = True
        sel.files = [_whole(f, sel.scores[f.key]) for f in sorted(files, key=lambda f: -sel.scores[f.key])]
        return sel

    ranked = sorted((f for f in files if sel.scores[f.key] > 0), key=lambda f: (-sel.scores[f.key], f.key))
    chosen: dict[str, SelectedFile] = {}
    remaining = budget_tokens

    def add(f: IngestedFile, cap: int | None = None) -> None:
        nonlocal remaining
        room = remaining if cap is None else min(cap, remaining)
        cost = estimate_tokens(f.text)
        if cost <= room:
            item = _whole(f, sel.scores[f.key])
        elif room >= MIN_USEFUL_TOKENS:
            item = _partial(f, control, sel.scores[f.key], room)
        else:
            return
        chosen[f.key] = item
        remaining -= item.tokens

    # Reserve a share for the best code-or-config file and the best document, so the model can
    # compare what documents claim with what the code does.
    for want in (("code", "config"), ("doc",)):
        best = next((f for f in ranked if f.kind in want and f.key not in chosen), None)
        if best:
            add(best, cap=budget_tokens // 3)
    for f in ranked:
        if f.key not in chosen:
            add(f)

    sel.files = sorted(chosen.values(), key=lambda s: (-s.score, s.key))
    sel.trimmed = [s.key for s in sel.files if not s.full]
    sel.left_out = [f.key for f in ranked if f.key not in chosen]
    relevant_cut = [k for k in sel.trimmed + sel.left_out if sel.scores[k] > 0.5]
    sel.coverage = "partial" if relevant_cut else "complete"
    return sel
