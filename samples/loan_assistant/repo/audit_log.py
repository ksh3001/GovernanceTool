"""Decision log: one JSON line per decision, kept for the bank's record-retention period."""
import hashlib
import json
import pathlib
from datetime import datetime, timezone

import yaml

CONFIG = yaml.safe_load(pathlib.Path(__file__).with_name("config.yaml").read_text())
LOG_FILE = pathlib.Path(CONFIG["audit"]["log_file"])
RETENTION_YEARS = CONFIG["audit"]["retention_years"]


def log_decision(applicant_id: str, features: dict, score: float, decision: str, model_version: str,
                 reviewer: str = "", note: str = "") -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "applicant_id": applicant_id,
        "features_sha256": hashlib.sha256(json.dumps(features, sort_keys=True).encode()).hexdigest(),
        "score": round(score, 4),
        "decision": decision,
        "model_version": model_version,
        "reviewer": reviewer,
        "note": note,
        "retention_years": RETENTION_YEARS,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
