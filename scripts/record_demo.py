"""Record the demo run: assess both sample apps with the live model and save the answers for replay.

    python scripts/record_demo.py

Needs PROVENIX_LLM_MODE=live and the AZURE_OPENAI_* values in .env. The answers are written to
demo/replay_cache.jsonl (commit it), and the result is compared with the expert answer keys, so this
one command is also the first accuracy measurement. Nothing from your own data/ folder is touched.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import load_settings  # noqa: E402
from core.demo import DEMO_CACHE, describe, run_samples  # noqa: E402
from core.llm import LLMClient  # noqa: E402


def main() -> int:
    settings = load_settings()
    if settings.llm_mode != "live":
        print("Set PROVENIX_LLM_MODE=live in .env first (and fill in the AZURE_OPENAI_* values).")
        return 2
    if not (settings.azure_endpoint and settings.azure_api_key and settings.azure_deployment):
        print("AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT must all be set in .env.")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        report = run_samples(LLMClient(dataclasses.replace(settings, data_dir=Path(tmp))))
        print("\n".join(describe(report)))
        if report.problems:
            print("\nNot saved: fix the problems above and run again.")
            return 1
        recorded = Path(tmp) / "replay" / "cache.jsonl"
        entries = {}
        for line in recorded.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            entries[entry["key"]] = entry["text"]

    DEMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DEMO_CACHE.write_text("".join(json.dumps({"key": k, "text": entries[k]}) + "\n" for k in sorted(entries)),
                          encoding="utf-8")
    print(f"\nSaved {len(entries)} recorded answers to {DEMO_CACHE}.")
    print("Look at the results above before you commit this file: the demo will show exactly these answers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
