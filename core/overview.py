"""Numbers for the Overview page: one row per application, plus totals across all of them.

Everything here is read from files already saved by the assessment and review steps.
The compliance score is our own internal metric, not an official EU measure.
"""
from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from .findings import STATUS_LABELS, FindingsFile, findings_path
from .models import AppRecord
from .onboarding import load_questionnaire
from .review import ReviewFile, review_path
from .scope import ScopeFile, scope_path
from .scoring import summarise
from .store import Store
from .tiers import load_classifier

GAP_STATUSES = ("not_met", "insufficient_evidence")


class AppRow(BaseModel):
    app_id: str
    name: str
    purpose: str = ""
    repo: str = ""
    framework: str = ""  # the first framework, used for shortcuts
    tier: str = ""
    tier_label: str = ""
    assessed: bool = False
    score: float | None = None  # mean over the frameworks that were assessed
    reviewed: int = 0
    total: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    placeholder: bool = False  # results came from the fake model
    scope_finalised: bool = False  # the rule scope of the first framework is finalised


class Activity(BaseModel):
    at: str
    app: str
    title: str
    detail: str = ""
    status: str = ""  # a status key for the pill, or "completed"


class NextAction(BaseModel):
    app_id: str
    app: str
    framework: str
    section: str  # Scope, Run, Review or Report: the step to open
    text: str


class GapRow(BaseModel):
    article: str
    title: str
    apps: int  # number of applications with this gap


class Overview(BaseModel):
    rows: list[AppRow] = Field(default_factory=list)
    top_gaps: list[GapRow] = Field(default_factory=list)
    activity: list[Activity] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)

    @property
    def assessed_apps(self) -> int:
        return sum(r.assessed for r in self.rows)

    @property
    def avg_score(self) -> float | None:
        scores = [r.score for r in self.rows if r.score is not None]
        return sum(scores) / len(scores) if scores else None

    @property
    def reviewed(self) -> int:
        return sum(r.reviewed for r in self.rows)

    @property
    def total(self) -> int:
        return sum(r.total for r in self.rows)

    @property
    def status_counts(self) -> dict[str, int]:
        return {s: sum(r.counts.get(s, 0) for r in self.rows) for s in STATUS_LABELS}

    @property
    def gap_total(self) -> int:
        counts = self.status_counts
        return sum(counts[s] for s in GAP_STATUSES)


def _next_action(row: AppRow) -> NextAction:
    left = row.total - row.reviewed
    if not row.assessed and not row.scope_finalised:
        section, text = "Scope", f"Confirm the rule scope for {row.name}"
    elif not row.assessed:
        section, text = "Run", f"Run the assessment for {row.name}"
    elif left > 0:
        section, text = "Review", f"Review {left} finding{'s' if left != 1 else ''} for {row.name}"
    else:
        section, text = "Report", f"Download the report for {row.name}"
    return NextAction(app_id=row.app_id, app=row.name, framework=row.framework, section=section, text=text)


def build_overview(store: Store, apps: list[AppRecord], packs_dir) -> Overview:
    rows: list[AppRow] = []
    gap_apps: Counter[tuple[str, str]] = Counter()
    activity: list[Activity] = []
    for app in apps:
        q = load_questionnaire(store, app.app_id)
        row = AppRow(app_id=app.app_id, name=app.name, purpose=q.purpose if q else "", repo=app.repo_url or app.repo_path,
                     framework=app.frameworks[0] if app.frameworks else "")
        scores: list[float] = []
        if row.framework:
            scope = store.load(app.app_id, scope_path(row.framework), ScopeFile)
            row.scope_finalised = bool(scope and scope.finalised)
        for fw in app.frameworks:
            classify = load_classifier(packs_dir / fw)
            if q and classify and not row.tier:
                result = classify(q)
                row.tier, row.tier_label = result.tier, result.label
            findings = store.load(app.app_id, findings_path(fw), FindingsFile)
            if findings is None:
                continue
            review = store.load(app.app_id, review_path(fw), ReviewFile)
            s = summarise(findings, review)
            if findings.finished_at:
                activity.append(Activity(at=findings.finished_at, app=app.name, title="Assessment completed",
                                         detail=f"{len(findings.reviewable)} rules in scope · {findings.llm_mode} mode", status="completed"))
            by_control = findings.by_control()
            for d in (review.history if review else []):
                f = by_control.get(d.control_id)
                activity.append(Activity(at=d.at, app=app.name, title=f"Finding {d.decision}",
                                         detail=(f"{f.article} · {f.title}" if f else d.control_id) + f" · by {d.reviewer}",
                                         status=d.final_status))
            row.assessed = True
            row.reviewed += s.reviewed
            row.total += len(findings.reviewable)
            row.placeholder = row.placeholder or findings.llm_mode == "fake"
            for status, n in s.counts.items():
                row.counts[status] = row.counts.get(status, 0) + n
            if s.score is not None:
                scores.append(s.score)
            for gap in s.gaps:
                gap_apps[(gap.article, gap.title)] += 1
        row.score = sum(scores) / len(scores) if scores else None
        rows.append(row)
    top = [GapRow(article=a, title=t, apps=n) for (a, t), n in gap_apps.most_common(5)]
    activity.sort(key=lambda a: a.at, reverse=True)
    return Overview(rows=rows, top_gaps=top, activity=activity[:6], next_actions=[_next_action(r) for r in rows][:4])
