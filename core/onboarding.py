"""Validate and save a newly onboarded application."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable

from .answer_key import find_answer_key
from .fetch import FetchedRepo, FetchError, _remove_tree, clone_repo, validate_repo_url
from .models import AppRecord
from .questionnaire import Questionnaire
from .store import Store

QUESTIONNAIRE_FILE = "questionnaire.json"

Fetcher = Callable[[str, Path], FetchedRepo]


def check_folder(raw: str, label: str, required: bool) -> tuple[str, str | None]:
    """Return (resolved path, error). An empty optional folder is fine."""
    raw = raw.strip().strip('"')
    if not raw:
        return "", (f"{label} is required." if required else None)
    path = Path(raw).expanduser()
    if not path.is_dir():
        return "", f"{label}: '{raw}' is not a folder on this machine."
    return str(path.resolve()), None


def onboard_application(store: Store, *, name: str, repo_path: str = "", repo_url: str = "",
                        docs_path: str = "", questionnaire: Questionnaire, frameworks: list[str],
                        user: str, fetcher: Fetcher = clone_repo,
                        samples_dir: Path | None = None) -> AppRecord:
    """Save a new application from either a local repo folder or a public repo URL."""
    errors: list[str] = []
    if not name.strip():
        errors.append("Application name is required.")
    repo, repo_url = "", repo_url.strip()
    if repo_path.strip() and repo_url:
        errors.append("Provide either a repository folder or a repository URL, not both.")
    elif repo_url:
        try:
            repo_url = validate_repo_url(repo_url)
        except FetchError as exc:
            errors.append(str(exc))
    else:
        repo, err = check_folder(repo_path, "Repository folder (or give a repository URL)", required=True)
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

    commit, checkout = "", None
    if repo_url:  # fetch before saving anything, so a failed fetch leaves no half-created app
        checkout = store.root.parent / "checkouts" / f"tmp-{uuid.uuid4().hex[:12]}"
        fetched = fetcher(repo_url, checkout)  # raises FetchError with a user-safe message
        repo_url, commit = fetched.url, fetched.commit
        repo = str(checkout)
    record = store.create_app(name.strip(), repo_path=repo, repo_url=repo_url, repo_commit=commit,
                              docs_path=docs, frameworks=frameworks, created_by=user)
    if checkout is not None:
        final = store.root.parent / "checkouts" / record.app_id
        _remove_tree(final)
        os.replace(checkout, final)
        record.repo_path = str(final.resolve())
    if samples_dir and repo_url:
        key = find_answer_key(samples_dir, repo_url)
        record.answer_key_path = str(key) if key else ""
    store.save(record.app_id, "app.json", record)
    store.save(record.app_id, QUESTIONNAIRE_FILE, questionnaire)
    return record


def load_questionnaire(store: Store, app_id: str) -> Questionnaire | None:
    return store.load(app_id, QUESTIONNAIRE_FILE, Questionnaire)
