"""Risk-tier result types, pack classifier loading and control applicability.

Tiers are decided by plain Python rules in each pack's tier_rules.py.
The model never decides a tier.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from .controls import Control
from .questionnaire import Questionnaire

TIER_LABELS = {
    "prohibited": "Prohibited",
    "high": "High risk",
    "limited": "Limited risk",
    "minimal": "Minimal risk",
    "out_of_scope": "Out of scope",
}


class RuleStep(BaseModel):
    rule_id: str
    question: str
    matched: bool
    detail: str = ""


class TierResult(BaseModel):
    tier: str
    rule_id: str
    legal_basis: str
    reason: str
    source_url: str
    steps: list[RuleStep] = Field(default_factory=list)  # every rule checked, in order

    @property
    def label(self) -> str:
        return TIER_LABELS.get(self.tier, self.tier)


class Applicability(BaseModel):
    control_id: str
    applies: bool
    reason: str = ""


Classifier = Callable[[Questionnaire], TierResult]


def load_classifier(pack_dir: Path) -> Classifier | None:
    """Return the pack's classify() function, or None if the pack has no tier rules."""
    path = Path(pack_dir) / "tier_rules.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"tier_rules_{Path(pack_dir).name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify


def control_applicability(controls: list[Control], tier: str, q: Questionnaire) -> list[Applicability]:
    """Decide in code which controls apply, so 'not applicable' is never left to the model."""
    out = []
    for c in controls:
        if tier in ("prohibited", "out_of_scope"):
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"Not assessed: the system is {TIER_LABELS[tier].lower()}."))
        elif tier not in c.applies_to_tiers:
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"{c.article} does not apply to {TIER_LABELS[tier].lower()} systems."))
        elif c.applies_if and not getattr(q, c.applies_if):
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"{c.article} applies only when the system {_FLAG_TEXT.get(c.applies_if, c.applies_if)}."))
        else:
            out.append(Applicability(control_id=c.id, applies=True))
    return out


_FLAG_TEXT = {
    "interacts_with_people": "interacts directly with people",
    "generates_synthetic_content": "generates synthetic content",
}
