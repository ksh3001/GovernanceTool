"""Check that the demo works offline: replay both sample apps from the saved cache.

    python scripts/check_demo.py

Makes no network calls. Run it before every demo and after any change to prompts, controls, search terms
or the sample apps, because those change the prompts and the saved answers stop matching.
"""
from __future__ import annotations

import dataclasses
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import load_settings  # noqa: E402
from core.demo import DEMO_CACHE, describe, run_samples  # noqa: E402
from core.llm import LLMClient  # noqa: E402


def main() -> int:
    settings = load_settings()
    cache = settings.replay_cache or DEMO_CACHE
    if not Path(cache).is_file():
        print(f"No saved demo run at {cache}.\nRecord one with: python scripts/record_demo.py (needs the Azure keys).")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        replay = dataclasses.replace(settings, llm_mode="replay", data_dir=Path(tmp))
        report = run_samples(LLMClient(replay))
    print("\n".join(describe(report)))
    if report.problems:
        print("\nDEMO NOT READY: the saved run no longer matches the app. Record it again with scripts/record_demo.py.")
        return 1
    print("\nDEMO READY: every call was answered from the saved run, no network used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
