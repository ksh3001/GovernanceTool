"""Risk-tier result types, pack classifier loading and control applicability.

Tiers are decided by plain Python rules in each pack's tier_rules.py.
The model never decides a tier.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable, Literal

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
    reason: str = ""  # why it applies, or why not
    decided_by: Literal["rule", "user"] = "rule"


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
    """Decide in code which controls apply, so 'not applicable' is never left to the model.

    Three filters, in order: the risk tier, the organisation's role (provider or deployer),
    and any questionnaire flag the control depends on. Each result carries a plain reason.
    """
    out = []
    tier_text = {"high": "high-risk", "limited": "limited-risk", "minimal": "minimal-risk"}.get(
        tier, TIER_LABELS.get(tier, tier).lower())
    for c in controls:
        if c.origin == "custom":
            out.append(Applicability(control_id=c.id, applies=True, reason="Custom rule added for this application.",
                                     decided_by="user"))
            continue
        roles = [r for r in c.applies_to_roles if (r == "provider" and q.is_provider) or (r == "deployer" and q.is_deployer)]
        flags = [f for f in c.conditions if getattr(q, f, False)]
        if tier in ("prohibited", "out_of_scope"):
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"Not assessed: the system is {tier_text}."))
        elif tier not in c.applies_to_tiers:
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"{c.article} does not apply to {tier_text} systems."))
        elif not roles:
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"{c.article} is a duty of the {' or '.join(c.applies_to_roles)}, "
                                            f"and you are the {ROLE_TEXT[q.role]}."))
        elif c.conditions and not flags:
            out.append(Applicability(control_id=c.id, applies=False,
                                     reason=f"{c.article} applies only when the system "
                                            f"{' or '.join(flag_text(f) for f in c.conditions)}."))
        else:
            parts = [f"{tier_text} system" if len(c.applies_to_tiers) < 4 else "every AI system in scope",
                     f"you are the {' and '.join(roles)}"]
            parts += [f"it {flag_text(f)}" for f in flags]
            out.append(Applicability(control_id=c.id, applies=True, reason="Applies: " + "; ".join(parts) + "."))
    return out


ROLE_TEXT = {"provider": "provider", "deployer": "deployer", "provider_and_deployer": "provider and deployer"}

_FLAG_TEXT = {
    "interacts_with_people": "interacts directly with people",
    "generates_synthetic_content": "generates synthetic content",
    "public_body_or_service": "is used by a public body or a provider of public services",
    "credit_or_insurance": "assesses creditworthiness or prices life or health insurance",
    "fria_trigger": "is used by a public body, a public-service provider, or for credit or insurance decisions",
    "emotion_or_biometric_categorisation": "recognises emotions or categorises people by biometrics",
    "deep_fake": "generates or manipulates deep-fake image, audio or video",
    "gpai_model": "is a general-purpose AI model you provide",
    "gpai_systemic_risk": "is a general-purpose AI model with systemic risk",
}


def flag_text(flag: str) -> str:
    return _FLAG_TEXT.get(flag, flag.replace("_", " "))
