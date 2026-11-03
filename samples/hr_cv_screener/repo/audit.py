"""Audit log: one JSON line per screening decision."""
import json
import time
from datetime import datetime, timezone

LOG_FILE = "audit_log.jsonl"
RETENTION_DAYS = 365


def log_decision(candidate_id: str, score: int, decision: str, model_version: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "score": score,
        "decision": decision,
        "model_version": model_version,
        "retention_days": RETENTION_DAYS,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def purge_old_entries(now: float | None = None) -> int:
    """Drop log lines older than the retention period. Returns how many were removed."""
    now = now or time.time()
    kept, removed = [], 0
    with open(LOG_FILE, encoding="utf-8") as fh:
        for line in fh:
            ts = datetime.fromisoformat(json.loads(line)["timestamp"]).timestamp()
            if now - ts > RETENTION_DAYS * 86400:
                removed += 1
            else:
                kept.append(line)
    with open(LOG_FILE, "w", encoding="utf-8") as fh:
        fh.writelines(kept)
    return removed
