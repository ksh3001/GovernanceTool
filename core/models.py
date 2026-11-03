"""Pydantic models persisted as JSON under data/apps/<app_id>/."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AppRecord(BaseModel):
    app_id: str
    name: str
    repo_path: str = ""
    docs_path: str = ""
    frameworks: list[str] = Field(default_factory=list)
    answer_key_path: str = ""  # set only for bundled sample apps
    created_by: str = ""
    created_at: str = Field(default_factory=_now)


class PackInfo(BaseModel):
    id: str
    name: str
    version: str
    source: str = ""
    source_url: str = ""
    has_tiers: bool = False
    status: str = "draft"
    reviewer: str | None = None
    reviewed_on: str | None = None
    description: str = ""
    available: bool = True
