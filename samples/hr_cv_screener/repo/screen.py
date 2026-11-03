"""CV screening tool: ranks job applicants with an LLM and notifies candidates.

Sample application A for the Provenix demo. Fictional.
"""
import json
import pathlib

import yaml

from audit import log_decision
from llm_client import chat  # thin wrapper around the company LLM endpoint

CONFIG = yaml.safe_load(pathlib.Path(__file__).with_name("config.yaml").read_text())
REJECT_BELOW = CONFIG["screening"]["reject_below_score"]
MODEL_VERSION = CONFIG["model"]["name"]

PROMPT = """You are a recruitment assistant. Score the CV from 0 to 100 for the job
description. Reply with JSON only: {"score": <int>, "summary": "<one sentence>"}.

JOB DESCRIPTION:
%s

CV:
%s
"""


def score_cv(job_description: str, cv_text: str) -> dict:
    """Ask the model for a score. Retries if the reply is not valid JSON."""
    for _ in range(3):
        reply = chat(PROMPT % (job_description, cv_text))
        try:
            data = json.loads(reply)
            data["score"] = max(0, min(100, int(data["score"])))
            return data
        except (ValueError, KeyError, TypeError):
            continue
    return {"score": 0, "summary": "unparseable model reply"}


def send_email(candidate_id: str, template: str) -> None:
    print(f"email {template} -> {candidate_id}")  # replaced by the mail service in production


def screen_candidate(candidate_id: str, job_description: str, cv_text: str) -> str:
    result = score_cv(job_description, cv_text)
    if result["score"] < REJECT_BELOW:
        decision = "reject"
        send_email(candidate_id, "rejection")  # sent immediately, no review step
    else:
        decision = "shortlist"
        send_email(candidate_id, "invite_to_interview")
    log_decision(candidate_id, result["score"], decision, MODEL_VERSION)
    return decision


def screen_folder(folder: str, job_description: str) -> dict:
    counts = {"reject": 0, "shortlist": 0}
    for cv_file in sorted(pathlib.Path(folder).glob("*.txt")):
        decision = screen_candidate(cv_file.stem, job_description, cv_file.read_text())
        counts[decision] += 1
    return counts
