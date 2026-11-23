"""Rule scope: which controls an application is assessed against.

The questionnaire proposes the scope (decided in code by tiers.control_applicability).
A person then reviews it: removes a rule that does not apply in practice, adds back a
rule the questionnaire ruled out, or adds a custom rule (for example an internal policy).
Every change needs a reason and is kept in an audit trail. The assessment only runs on a
finalised scope, and the report shows the scope and every change made to it.

Saved per application and framework as scope/<framework>.json.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from .controls import Control
from .findings import now
from .tiers import Applicability

STOPWORDS = {"the", "and", "for", "with", "that", "this", "must", "shall", "should", "have", "from", "into",
             "each", "every", "are", "is", "be", "been", "being", "its", "their", "there", "where", "when",
             "which", "will", "would", "about", "after", "before", "under", "over", "all", "any", "not", "only",
             "such", "than", "them", "they", "what", "who", "how", "our", "your", "you", "can", "may", "use",
             "used", "using", "also", "has", "had", "was", "were", "does", "done"}

Evidence = Literal["code", "document", "both"]


class ScopeChange(BaseModel):
    control_id: str
    action: Literal["exclude", "include"]  # exclude a rule the questionnaire applied, include one it ruled out
    reason: str
    by: str
    at: str = Field(default_factory=now)


class CustomRule(BaseModel):
    id: str
    reference: str  # e.g. "Internal policy AI-07" or "Article 26(7)"
    title: str
    requirement: str  # what must be true, in plain words
    expected_evidence: Evidence = "both"
    search_terms: list[str]
    remediation: list[str] = Field(default_factory=list)
    reason: str = ""
    by: str
    at: str = Field(default_factory=now)


class ScopeEvent(BaseModel):
    at: str = Field(default_factory=now)
    by: str
    action: str  # excluded, included, reverted, custom_added, custom_removed, finalised, reopened
    control_id: str = ""
    detail: str = ""


class ScopeFile(BaseModel):
    app_id: str
    framework: str
    status: Literal["draft", "finalised"] = "draft"
    finalised_by: str = ""
    finalised_at: str = ""
    changes: dict[str, ScopeChange] = Field(default_factory=dict)
    custom: list[CustomRule] = Field(default_factory=list)
    history: list[ScopeEvent] = Field(default_factory=list)

    @property
    def finalised(self) -> bool:
        return self.status == "finalised"


def scope_path(framework: str) -> str:
    return f"scope/{framework}.json"


def new_scope(app_id: str, framework: str) -> ScopeFile:
    return ScopeFile(app_id=app_id, framework=framework)


# ---------- turning a scope into controls and applicability ----------

def custom_control(rule: CustomRule) -> Control:
    return Control(id=rule.id, article=rule.reference, title=rule.title, paraphrase=rule.requirement, quote="",
                   source_url="", expected_evidence=rule.expected_evidence,
                   applies_to_tiers=["high", "limited", "minimal"], search_terms=rule.search_terms,
                   remediation=rule.remediation, origin="custom")


class ScopedRule(BaseModel):
    control: Control
    applies: bool
    reason: str
    proposed: bool  # what the questionnaire said, before any change
    change: Literal["", "added", "removed", "custom"] = ""
    change_reason: str = ""
    changed_by: str = ""


def scoped_rules(controls: list[Control], applicability: list[Applicability], scope: ScopeFile | None) -> list[ScopedRule]:
    """Every rule with its final in/out decision and where that decision came from."""
    proposed = {a.control_id: a for a in applicability}
    changes = scope.changes if scope else {}
    out = []
    for c in controls:
        a = proposed[c.id]
        ch = changes.get(c.id)
        if ch and ch.action == "exclude" and a.applies:
            out.append(ScopedRule(control=c, applies=False, reason=f"Removed from scope by {ch.by}: {ch.reason}",
                                  proposed=True, change="removed", change_reason=ch.reason, changed_by=ch.by))
        elif ch and ch.action == "include" and not a.applies:
            out.append(ScopedRule(control=c, applies=True, reason=f"Added to scope by {ch.by}: {ch.reason}",
                                  proposed=False, change="added", change_reason=ch.reason, changed_by=ch.by))
        else:
            out.append(ScopedRule(control=c, applies=a.applies, reason=a.reason, proposed=a.applies))
    for rule in scope.custom if scope else []:
        out.append(ScopedRule(control=custom_control(rule), applies=True,
                              reason=f"Custom rule added by {rule.by}" + (f": {rule.reason}" if rule.reason else "."),
                              proposed=False, change="custom", change_reason=rule.reason, changed_by=rule.by))
    return out


def effective_scope(controls: list[Control], applicability: list[Applicability],
                    scope: ScopeFile | None) -> tuple[list[Control], list[Applicability]]:
    """Controls and applicability after the reviewer's changes, ready for the assessment loop."""
    rules = scoped_rules(controls, applicability, scope)
    return ([r.control for r in rules],
            [Applicability(control_id=r.control.id, applies=r.applies, reason=r.reason,
                           decided_by="user" if r.change else "rule") for r in rules])


class ScopeSummary(BaseModel):
    in_scope: int
    out_of_scope: int
    proposed: int  # what the questionnaire proposed
    removed: int
    added: int
    custom: int


def summarise_scope(rules: list[ScopedRule]) -> ScopeSummary:
    return ScopeSummary(in_scope=sum(r.applies for r in rules), out_of_scope=sum(not r.applies for r in rules),
                        proposed=sum(r.proposed for r in rules), removed=sum(r.change == "removed" for r in rules),
                        added=sum(r.change == "added" for r in rules), custom=sum(r.change == "custom" for r in rules))


# ---------- changes (each raises ValueError with a message safe to show) ----------

def _require_draft(scope: ScopeFile) -> None:
    if scope.finalised:
        raise ValueError("The scope is finalised. Reopen it to make changes.")


def _clean_reason(reason: str, what: str) -> str:
    reason = " ".join(reason.split())
    if len(reason) < 5:
        raise ValueError(f"Give a short reason for {what} (it is kept in the audit trail and shown in the report).")
    return reason[:500]


def exclude_rule(scope: ScopeFile, control_id: str, reason: str, by: str) -> None:
    _require_draft(scope)
    reason = _clean_reason(reason, "removing this rule")
    scope.changes[control_id] = ScopeChange(control_id=control_id, action="exclude", reason=reason, by=by)
    scope.history.append(ScopeEvent(by=by, action="excluded", control_id=control_id, detail=reason))


def include_rule(scope: ScopeFile, control_id: str, reason: str, by: str) -> None:
    _require_draft(scope)
    reason = _clean_reason(reason, "adding this rule")
    scope.changes[control_id] = ScopeChange(control_id=control_id, action="include", reason=reason, by=by)
    scope.history.append(ScopeEvent(by=by, action="included", control_id=control_id, detail=reason))


def revert_rule(scope: ScopeFile, control_id: str, by: str) -> None:
    _require_draft(scope)
    if scope.changes.pop(control_id, None):
        scope.history.append(ScopeEvent(by=by, action="reverted", control_id=control_id,
                                        detail="Back to the questionnaire's proposal"))


def keywords(*texts: str, limit: int = 10) -> list[str]:
    """Search terms for a custom rule when the user gives none: distinctive words from its text."""
    seen: list[str] = []
    for text in texts:
        for word in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower()):
            if word not in STOPWORDS and word not in seen:
                seen.append(word)
    return seen[:limit]


def add_custom_rule(scope: ScopeFile, *, reference: str, title: str, requirement: str, expected_evidence: str,
                    search_terms: str = "", remediation: str = "", reason: str = "", by: str) -> CustomRule:
    _require_draft(scope)
    reference, title, requirement = reference.strip(), title.strip(), " ".join(requirement.split())
    errors = []
    if len(title) < 4:
        errors.append("Give the rule a title.")
    if len(requirement) < 20:
        errors.append("Describe what must be true, in a sentence or two (at least 20 characters).")
    if expected_evidence not in ("code", "document", "both"):
        errors.append("Choose where the evidence is expected.")
    if errors:
        raise ValueError("\n".join(errors))
    terms = [t.strip().lower() for t in search_terms.split(",") if t.strip()] or keywords(title, requirement)
    if not terms:
        raise ValueError("Add a few keywords so the tool can find the relevant files.")
    base = "custom-" + (re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30] or "rule")
    taken = {r.id for r in scope.custom}
    rule_id, n = base, 2
    while rule_id in taken:
        rule_id, n = f"{base}-{n}", n + 1
    rule = CustomRule(id=rule_id, reference=reference or "Custom rule", title=title, requirement=requirement,
                      expected_evidence=expected_evidence, search_terms=terms[:12],
                      remediation=[s.strip(" -•\t") for s in remediation.splitlines() if s.strip(" -•\t")],
                      reason=" ".join(reason.split())[:500], by=by)
    scope.custom.append(rule)
    scope.history.append(ScopeEvent(by=by, action="custom_added", control_id=rule_id, detail=title))
    return rule


def remove_custom_rule(scope: ScopeFile, rule_id: str, by: str) -> None:
    _require_draft(scope)
    before = len(scope.custom)
    scope.custom = [r for r in scope.custom if r.id != rule_id]
    if len(scope.custom) != before:
        scope.history.append(ScopeEvent(by=by, action="custom_removed", control_id=rule_id))


def finalise(scope: ScopeFile, rules: list[ScopedRule], by: str) -> None:
    _require_draft(scope)
    if not any(r.applies for r in rules):
        raise ValueError("No rule is in scope, so there is nothing to assess. Add a rule or revisit the questionnaire.")
    scope.status, scope.finalised_by, scope.finalised_at = "finalised", by, now()
    summary = summarise_scope(rules)
    scope.history.append(ScopeEvent(by=by, action="finalised",
                                    detail=f"{summary.in_scope} rules in scope ({summary.removed} removed, "
                                           f"{summary.added} added, {summary.custom} custom)"))


def reopen(scope: ScopeFile, by: str) -> None:
    if not scope.finalised:
        return
    scope.status, scope.finalised_by, scope.finalised_at = "draft", "", ""
    scope.history.append(ScopeEvent(by=by, action="reopened"))


class Preview(BaseModel):
    framework: str
    tier: str = ""
    tier_label: str = ""
    legal_basis: str = ""
    reason: str = ""
    rules: list[tuple[str, str]] = Field(default_factory=list)  # (article, title) that apply
    total: int = 0


def preview(q, pack_dir) -> Preview:
    """What the questionnaire, as answered so far, would put in scope. Used for the live preview."""
    from pathlib import Path

    from .controls import load_controls
    from .tiers import control_applicability, load_classifier

    pack_dir = Path(pack_dir)
    classify = load_classifier(pack_dir)
    tier = classify(q) if classify else None
    controls = load_controls(pack_dir)
    applic = {a.control_id: a for a in control_applicability(controls, tier.tier if tier else "high", q)}
    return Preview(framework=pack_dir.name, tier=tier.tier if tier else "", tier_label=tier.label if tier else "",
                   legal_basis=tier.legal_basis if tier else "", reason=tier.reason if tier else "",
                   rules=[(c.article, c.title) for c in controls if applic[c.id].applies], total=len(controls))
