"""Pre-approval decision: score with the credit model, then approve, decline or refer."""
import pathlib
from dataclasses import dataclass

import yaml

from audit_log import log_decision
from features import build_features
from model import load_model

CONFIG = yaml.safe_load(pathlib.Path(__file__).with_name("config.yaml").read_text())
APPROVE_AT = CONFIG["decision"]["approve_at_or_above"]
DECLINE_BELOW = CONFIG["decision"]["decline_below"]
MODEL = load_model(CONFIG["model"]["path"])
MODEL_VERSION = f'{CONFIG["model"]["name"]}-{CONFIG["model"]["version"]}'


@dataclass
class Outcome:
    decision: str  # approve | decline | refer
    score: float
    customer_message: str


def send_letter(applicant_id: str, template: str) -> None:
    print(f"letter {template} -> {applicant_id}")  # replaced by the correspondence service in production


def queue_for_underwriter(applicant_id: str, score: float, features: dict) -> None:
    print(f"underwriter queue <- {applicant_id} ({score:.2f})")  # replaced by the case system


def decide(applicant_id: str, answers: dict[str, str]) -> Outcome:
    features = build_features(answers)
    score = float(MODEL.predict_proba(features))
    if score >= APPROVE_AT:
        decision, message = "approve", "Good news: you are pre-approved. A lending advisor will confirm the offer."
    elif score < DECLINE_BELOW:
        decision, message = "decline", "We are unable to pre-approve this loan. We will send you a letter explaining why."
        send_letter(applicant_id, "decline")  # automatic, no underwriter review
    else:
        decision, message = "refer", "An underwriter will review your application within two working days."
        queue_for_underwriter(applicant_id, score, features)
    log_decision(applicant_id, features, score, decision, MODEL_VERSION)
    return Outcome(decision=decision, score=score, customer_message=message)


def underwriter_override(applicant_id: str, new_decision: str, underwriter: str, reason: str) -> None:
    """Underwriters can change any referred decision; the change is logged with their name."""
    if new_decision not in {"approve", "decline"}:
        raise ValueError("decision must be approve or decline")
    if not reason.strip():
        raise ValueError("a reason is required")
    log_decision(applicant_id, {}, -1.0, new_decision, MODEL_VERSION, reviewer=underwriter, note=reason)
