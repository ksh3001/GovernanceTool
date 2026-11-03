"""Discover control packs from control_packs/*/pack.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import PackInfo

# Shown greyed out in the picker to show the design supports more frameworks.
COMING_SOON = [
    ("iso_42001", "ISO/IEC 42001", "AI management system standard"),
    ("nist_ai_rmf", "NIST AI RMF", "US risk management framework"),
]


def discover_packs(packs_dir: Path) -> list[PackInfo]:
    packs: list[PackInfo] = []
    if packs_dir.is_dir():
        for pack_file in sorted(packs_dir.glob("*/pack.yaml")):
            raw = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
            packs.append(PackInfo(**raw))
    found = {p.id for p in packs}
    for pid, name, desc in COMING_SOON:
        if pid not in found:
            packs.append(PackInfo(id=pid, name=name, version="", description=desc, available=False))
    return packs
