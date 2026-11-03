"""Install the bundled sample applications into the store."""
from __future__ import annotations

from pathlib import Path

from .answer_key import load_answer_key
from .models import AppRecord
from .onboarding import onboard_application
from .questionnaire import Questionnaire
from .store import Store


def install_samples(store: Store, samples_dir: Path, frameworks: list[str], user: str) -> list[AppRecord]:
    """Onboard each sample app that is not already present. Returns the newly added ones."""
    existing = {a.answer_key_path for a in store.list_apps() if a.answer_key_path}
    added = []
    for sample in sorted(Path(samples_dir).glob("*/answer_key.yaml")):
        key_path = str(sample.resolve())
        if key_path in existing:
            continue
        folder = sample.parent
        questionnaire = Questionnaire.model_validate_json((folder / "questionnaire.json").read_text(encoding="utf-8"))
        record = onboard_application(
            store, name=load_answer_key(sample).app_name, repo_path=str(folder / "repo"),
            docs_path=str(folder / "docs"), questionnaire=questionnaire, frameworks=frameworks, user=user)
        record.answer_key_path = key_path
        store.save(record.app_id, "app.json", record)
        added.append(record)
    return added
