"""Load and validate the controls of a framework pack."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Tier = Literal["prohibited", "high", "limited", "minimal"]


class Control(BaseModel):
    id: str
    article: str
    title: str
    paraphrase: str
    quote: str
    source_url: str
    expected_evidence: Literal["code", "document", "both"]
    applies_to_tiers: list[Tier]
    applies_if: str | None = None  # name of a questionnaire flag that must be true
    search_terms: list[str] = Field(min_length=1)

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
