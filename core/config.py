"""Settings from environment variables, with a minimal .env loader."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    llm_mode: str
    demo_password: str
    azure_endpoint: str
    azure_api_key: str
    azure_deployment: str
    azure_api_version: str
    data_dir: Path
    packs_dir: Path
    replay_cache: Path | None = None  # recorded demo responses, read in replay mode


def load_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    mode = os.environ.get("PROVENIX_LLM_MODE", "fake").lower()
    if mode not in {"fake", "live", "replay"}:
        raise ValueError(f"PROVENIX_LLM_MODE must be fake, live or replay, got {mode!r}")
    return Settings(
        llm_mode=mode,
        demo_password=os.environ.get("PROVENIX_DEMO_PASSWORD", ""),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        data_dir=Path(os.environ.get("PROVENIX_DATA_DIR", ROOT / "data")),
        packs_dir=Path(os.environ.get("PROVENIX_PACKS_DIR", ROOT / "control_packs")),
        replay_cache=Path(os.environ.get("PROVENIX_REPLAY_CACHE", ROOT / "demo" / "replay_cache.jsonl")),
    )
