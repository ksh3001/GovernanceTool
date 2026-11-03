"""Local JSON file store: one folder per application under data/apps/<app_id>/."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import AppRecord

M = TypeVar("M", bound=BaseModel)

_SLUG = re.compile(r"[^a-z0-9]+")


class Store:
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / "apps"
        self.root.mkdir(parents=True, exist_ok=True)

    def app_dir(self, app_id: str) -> Path:
        path = (self.root / app_id).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError(f"invalid app id {app_id!r}")
        return path

    def _unique_id(self, name: str) -> str:
        base = _SLUG.sub("-", name.lower()).strip("-") or "app"
        app_id, n = base, 2
        while (self.root / app_id).exists():
            app_id, n = f"{base}-{n}", n + 1
        return app_id

    def create_app(self, name: str, **fields) -> AppRecord:
        record = AppRecord(app_id=self._unique_id(name), name=name, **fields)
        self.save(record.app_id, "app.json", record)
        return record

    def list_apps(self) -> list[AppRecord]:
        return [AppRecord.model_validate_json(f.read_text(encoding="utf-8"))
                for f in sorted(self.root.glob("*/app.json"))]

    def get_app(self, app_id: str) -> AppRecord | None:
        return self.load(app_id, "app.json", AppRecord)

    def save(self, app_id: str, relpath: str, model: BaseModel) -> Path:
        path = self.app_dir(app_id) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def load(self, app_id: str, relpath: str, model_cls: type[M]) -> M | None:
        path = self.app_dir(app_id) / relpath
        if not path.is_file():
            return None
        return model_cls.model_validate_json(path.read_text(encoding="utf-8"))

    def append_log(self, app_id: str, name: str, entry: dict) -> None:
        path = self.app_dir(app_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
