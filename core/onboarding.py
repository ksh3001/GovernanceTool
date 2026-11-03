"""Validate and save a newly onboarded application."""
from __future__ import annotations

from pathlib import Path

from .models import AppRecord
from .questionnaire import Questionnaire
from .store import Store

QUESTIONNAIRE_FILE = "questionnaire.json"


def check_folder(raw: str, label: str, required: bool) -> tuple[str, str | None]:
    """Return (resolved path, error). An empty optional folder is fine."""
    raw = raw.strip().strip('"')
    if not raw:
        return "", (f"{label} is required." if required else None)
    path = Path(raw).expanduser()
    if not path.is_dir():
        return "", f"{label}: '{raw}' is not a folder on this machine."
    return str(path.resolve()), None


def onboard_application(store: Store, *, name: str, repo_path: str, docs_path: str,
                        questionnaire: Questionnaire, frameworks: list[str],
                        user: str) -> AppRecord:
    errors: list[str] = []
    if not name.strip():
        errors.append("Application name is required.")
    repo, err = check_folder(repo_path, "Repository folder", required=True)
    if err:
        errors.append(err)
    docs, err = check_folder(docs_path, "Documents folder", required=False)
    if err:
        errors.append(err)
    if not frameworks:
        errors.append("Select at least one framework.")
    errors += questionnaire.problems()
    if errors:
        raise ValueError("\n".join(errors))
    record = store.create_app(name.strip(), repo_path=repo, docs_path=docs,
                              frameworks=frameworks, created_by=user)
    store.save(record.app_id, QUESTIONNAIRE_FILE, questionnaire)
    return record


def load_questionnaire(store: Store, app_id: str) -> Questionnaire | None:
    return store.load(app_id, QUESTIONNAIRE_FILE, Questionnaire)
