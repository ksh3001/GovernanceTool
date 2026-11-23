"""Weekly monitoring job: approval rates by region, with an alert when they drift apart."""
import json
import pathlib
from collections import defaultdict

import yaml

CONFIG = yaml.safe_load(pathlib.Path(__file__).with_name("config.yaml").read_text())
GAP_ALERT = CONFIG["monitoring"]["approval_gap_alert"]


def approval_rates(log_file: str, region_of) -> dict[str, float]:
    totals, approved = defaultdict(int), defaultdict(int)
    for line in pathlib.Path(log_file).read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["reviewer"]:
            continue  # count model decisions only
        region = region_of(entry["applicant_id"])
        totals[region] += 1
        approved[region] += entry["decision"] == "approve"
    return {r: approved[r] / totals[r] for r in totals}


def weekly_check(log_file: str, region_of, alert) -> None:
    rates = approval_rates(log_file, region_of)
    if rates and max(rates.values()) - min(rates.values()) > GAP_ALERT:
        alert(f"Approval-rate gap between regions above {GAP_ALERT:.0%}: {rates}")
