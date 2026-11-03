"""Fetch a public repository by URL into a local folder, safely.

The code is only ever read, never run. The clone is shallow, has no submodules or
LFS content, uses HTTPS only, and cannot prompt for credentials (private repos
fail with a clear message). Private-repo support is out of scope for the POC.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

DEFAULT_HOSTS = ("github.com", "gitlab.com", "bitbucket.org")
CLONE_TIMEOUT_SECONDS = 120
MAX_CHECKOUT_MB = 100

_PATH = re.compile(r"^/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+?(\.git)?/?$")


class FetchError(ValueError):
    """The repository could not be fetched; the message is safe to show to users."""


class FetchedRepo(NamedTuple):
    path: Path
    url: str
    commit: str


def allowed_hosts() -> tuple[str, ...]:
    raw = os.environ.get("PROVENIX_GIT_HOSTS", "")
    hosts = tuple(h.strip().lower() for h in raw.split(",") if h.strip())
    return hosts or DEFAULT_HOSTS


def normalize_url(url: str) -> str:
    """Canonical form used to compare URLs: https://host/owner/repo without .git or slash."""
    p = urlparse(url.strip())
    path = p.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"https://{(p.hostname or '').lower()}{path}"


def validate_repo_url(url: str) -> str:
    """Return the cleaned URL or raise FetchError."""
    url = url.strip()
    p = urlparse(url)
    if p.scheme != "https":
        raise FetchError("Repository URL must start with https://")
    if p.username or p.password or "@" in p.netloc:
        raise FetchError("Repository URL must not contain credentials.")
    if p.query or p.fragment or p.port:
        raise FetchError("Repository URL must be a plain https://host/owner/repo address.")
    host = (p.hostname or "").lower()
    if host not in allowed_hosts():
        raise FetchError(f"Host '{host}' is not allowed. Allowed hosts: {', '.join(allowed_hosts())}.")
    if not _PATH.match(p.path):
        raise FetchError("Repository URL must look like https://github.com/owner/repo")
    return url


def _remove_tree(path: Path) -> None:
    """rmtree that also deletes read-only git object files (needed on Windows)."""
    def clear_readonly(func, p, _exc):
        os.chmod(p, 0o700)
        func(p)
    shutil.rmtree(path, onerror=clear_readonly) if path.exists() else None


def _folder_mb(path: Path) -> float:
    total = 0
    for root, dirs, files in os.walk(path):
        if ".git" in dirs:
            dirs.remove(".git")
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total / 1_000_000


def _git(args: list[str], cwd: Path | None = None, timeout: int = CLONE_TIMEOUT_SECONDS) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo", "GIT_LFS_SKIP_SMUDGE": "1"}
    try:
        done = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except FileNotFoundError:
        raise FetchError("git is not installed on this machine.") from None
    except subprocess.TimeoutExpired:
        raise FetchError(f"Fetching timed out after {timeout} seconds.") from None
    if done.returncode != 0:
        raise FetchError(_friendly(done.stderr))
    return done.stdout.strip()


def _friendly(stderr: str) -> str:
    text = stderr.lower()
    if "not found" in text or "could not read username" in text or "authentication" in text:
        return "Repository not found, or it is private. Only public repositories are supported."
    if "could not resolve host" in text or "unable to access" in text:
        return "Could not reach the host. Check the network connection."
    return "Git could not fetch this repository."


def clone_repo(url: str, dest: Path, *, max_mb: int = MAX_CHECKOUT_MB, _allow_local: bool = False) -> FetchedRepo:
    """Shallow-clone `url` into the new folder `dest`. `_allow_local` exists for tests only."""
    if not _allow_local:
        url = validate_repo_url(url)
    dest = Path(dest)
    if dest.exists():
        raise FetchError("Destination folder already exists.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["clone", "--depth", "1", "--single-branch", "--no-tags", "--template=",
            "-c", "filter.lfs.smudge=", "-c", "filter.lfs.required=false"]
    if not _allow_local:
        args += ["-c", "protocol.allow=never", "-c", "protocol.https.allow=always"]
    try:
        _git([*args, "--", url, str(dest)])
        size = _folder_mb(dest)
        if size > max_mb:
            raise FetchError(f"Repository is {size:.0f} MB, above the {max_mb} MB limit.")
        commit = _git(["rev-parse", "HEAD"], cwd=dest)
    except Exception:
        _remove_tree(dest)
        raise
    return FetchedRepo(path=dest, url=url, commit=commit)
