"""Load and validate the controls of a framework pack."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Tier = Literal["prohibited", "high", "limited", "minimal"]
Role = Literal["provider", "deployer"]


class Control(BaseModel):
    id: str
    article: str
    title: str
    paraphrase: str
    quote: str
    source_url: str
    expected_evidence: Literal["code", "document", "both"]
    applies_to_tiers: list[Tier]
    applies_to_roles: list[Role] = Field(default_factory=lambda: ["provider", "deployer"])
    # Questionnaire flag(s): the control applies only if at least one is true.
    applies_if: str | list[str] | None = None
    search_terms: list[str] = Field(min_length=1)
    remediation: list[str] = Field(default_factory=list)  # general steps to close a gap; written by us, expert-reviewed
    origin: Literal["pack", "custom"] = "pack"  # custom = added by a user for one application

    @property
    def conditions(self) -> list[str]:
        if not self.applies_if:
            return []
        return [self.applies_if] if isinstance(self.applies_if, str) else list(self.applies_if)

    @field_validator("quote")
    @classmethod
    def _short_quote(cls, v: str) -> str:
        if len(v) > 160:
            raise ValueError("quote must be a short fragment (160 characters or fewer)")
        return v


def load_controls(pack_dir: Path) -> list[Control]:
    raw = yaml.safe_load((Path(pack_dir) / "controls.yaml").read_text(encoding="utf-8")) or {}
    controls = [Control(**c) for c in raw.get("controls", [])]
    ids = [c.id for c in controls]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate control ids in controls.yaml")
    return controls
