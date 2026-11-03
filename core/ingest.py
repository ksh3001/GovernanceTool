"""Read an application's folders into memory. Nothing from the app is executed.

Only text and code files are kept. Everything skipped or unreadable is listed
with a reason, so nothing is dropped silently.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MAX_FILE_BYTES = 200_000
MAX_FILES = 500

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env", "dist", "build", "target",
             "__pycache__", ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".tox", "site-packages",
             ".next", "coverage"}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "pipfile.lock",
              "cargo.lock", "composer.lock", "go.sum", ".ds_store"}
SENSITIVE_NAMES = {"id_rsa", "id_ed25519", "credentials", "secrets.yaml", "secrets.yml", "secrets.json"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".kdbx"}

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".rs", ".cs", ".cpp", ".cc", ".c",
            ".h", ".hpp", ".php", ".kt", ".swift", ".scala", ".sql", ".sh", ".ps1", ".r", ".m", ".dart", ".html", ".css"}
CONFIG_EXT = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".properties"}
DOC_EXT = {".md", ".txt", ".rst"}
EXTRACTED_EXT = {".pdf", ".docx"}  # need an optional library

Kind = Literal["code", "doc", "config"]
Area = Literal["repo", "docs"]


class IngestedFile(BaseModel):
    area: Area
    path: str  # relative to its area root, forward slashes
    kind: Kind
    size: int
    lines: int
    sha256: str
    extracted: bool = False  # text came from a PDF/docx, so line numbers refer to the extracted text
    text: str = Field(default="", exclude=True)

    @property
    def key(self) -> str:
        return f"{self.area}:{self.path}"


class SkippedFile(BaseModel):
    area: Area
    path: str
    reason: str


class IngestResult(BaseModel):
    files: list[IngestedFile] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)
    unreadable: list[SkippedFile] = Field(default_factory=list)  # a reader exists but is not installed/failed

    def by_key(self) -> dict[str, IngestedFile]:
        return {f.key: f for f in self.files}


def _extract_pdf(path: Path) -> str:
    import fitz  # pymupdf
    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def _extract_docx(path: Path) -> str:
    import docx  # python-docx
    return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)


def _kind(area: Area, ext: str) -> Kind | None:
    if ext in DOC_EXT:
        return "doc"
    if area == "docs" and ext in EXTRACTED_EXT:
        return "doc"
    if ext in CONFIG_EXT:
        return "config"
    if ext in CODE_EXT and area == "repo":
        return "code"
    return None


def _walk(root: Path, area: Area, result: IngestResult, budget: list[int]) -> None:
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames
                             if d.lower() not in SKIP_DIRS and not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            lower, ext = name.lower(), full.suffix.lower()

            def skip(reason: str, bucket: list | None = None) -> None:
                (result.skipped if bucket is None else bucket).append(SkippedFile(area=area, path=rel, reason=reason))

            if full.is_symlink():
                skip("symbolic link")
            elif lower in SKIP_NAMES:
                skip("lock or system file")
            elif lower.startswith(".env") or lower in SENSITIVE_NAMES or ext in SENSITIVE_SUFFIXES:
                skip("may contain secrets")
            elif ".min." in lower:
                skip("minified file")
            elif (kind := _kind(area, ext)) is None:
                skip(f"file type {ext or '(none)'} not analysed")
            elif budget[0] <= 0:
                skip(f"file limit of {MAX_FILES} reached")
            elif full.stat().st_size > MAX_FILE_BYTES:
                skip(f"larger than {MAX_FILE_BYTES // 1000} KB")
            else:
                _read(full, rel, area, kind, ext, result, budget, skip)


def _read(full, rel, area, kind, ext, result, budget, skip) -> None:
    raw = full.read_bytes()
    extracted = ext in EXTRACTED_EXT
    if extracted:
        extractor = _extract_pdf if ext == ".pdf" else _extract_docx
        try:
            text = extractor(full)
        except ImportError:
            lib = "pymupdf" if ext == ".pdf" else "python-docx"
            skip(f"cannot read {ext} files: install {lib}", result.unreadable)
            return
        except Exception as exc:  # corrupt or encrypted document
            skip(f"cannot read file ({type(exc).__name__})", result.unreadable)
            return
    else:
        if b"\x00" in raw[:4096]:
            skip("binary file")
            return
        text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        skip("empty file")
        return
    budget[0] -= 1
    result.files.append(IngestedFile(area=area, path=rel, kind=kind, size=len(raw), lines=len(text.splitlines()),
                                     sha256=hashlib.sha256(raw).hexdigest(), extracted=extracted, text=text))


def ingest(repo_path: str | Path, docs_path: str | Path | None = None) -> IngestResult:
    """Walk the repo folder and the optional documents folder (symlinks are never followed)."""
    result = IngestResult()
    budget = [MAX_FILES]
    for root, area in ((repo_path, "repo"), (docs_path, "docs")):
        if root and Path(root).is_dir():
            _walk(Path(root), area, result, budget)  # type: ignore[arg-type]
    return result
