import shutil
import subprocess

import pytest

from core.answer_key import find_answer_key
from core.config import ROOT
from core.fetch import FetchedRepo, FetchError, clone_repo, normalize_url, validate_repo_url
from core.onboarding import onboard_application
from core.questionnaire import Questionnaire
from core.store import Store


@pytest.mark.parametrize("url", [
    "https://github.com/ksh3001/provenix-sample-hr-cv-screener",
    "https://github.com/ksh3001/provenix-sample-hr-cv-screener.git",
    "https://github.com/ksh3001/provenix-sample-hr-cv-screener/",
    "https://gitlab.com/group/project",
])
def test_valid_urls(url):
    assert validate_repo_url(url) == url


@pytest.mark.parametrize("url,msg", [
    ("http://github.com/a/b", "https"),
    ("git@github.com:a/b.git", "https"),
    ("file:///etc/passwd", "https"),
    ("ssh://github.com/a/b", "https"),
    ("https://user:token@github.com/a/b", "credentials"),
    ("https://token@github.com/a/b", "credentials"),
    ("https://evil.example.com/a/b", "not allowed"),
    ("https://github.com/a", "look like"),
    ("https://github.com/a/b/tree/main", "look like"),
    ("https://github.com/a/b?x=1", "plain"),
    ("https://github.com:8443/a/b", "plain"),
    ("https://github.com/-upload-pack=x/b", "look like"),
])
def test_rejected_urls(url, msg):
    with pytest.raises(FetchError, match=msg):
        validate_repo_url(url)


def test_normalize_matches_variants():
    a = normalize_url("https://GitHub.com/Owner/Repo.git")
    assert a == normalize_url("https://github.com/Owner/Repo/") == "https://github.com/Owner/Repo"


def make_local_repo(path):
    path.mkdir(parents=True)
    (path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run([*git, "add", "."], cwd=path, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], cwd=path, check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True).stdout.strip()


def test_clone_returns_commit_and_files(tmp_path):
    sha = make_local_repo(tmp_path / "src")
    got = clone_repo(str(tmp_path / "src"), tmp_path / "out", _allow_local=True)
    assert got.commit == sha and (got.path / "app.py").is_file()


def test_clone_size_limit_removes_checkout(tmp_path):
    make_local_repo(tmp_path / "src")
    (tmp_path / "src" / "big.bin").write_bytes(b"0" * 2_000_000)
    subprocess.run(["git", "add", "."], cwd=tmp_path / "src", check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "big"],
                   cwd=tmp_path / "src", check=True)
    with pytest.raises(FetchError, match="limit"):
        clone_repo(str(tmp_path / "src"), tmp_path / "out", max_mb=1, _allow_local=True)
    assert not (tmp_path / "out").exists()


def test_clone_failure_is_friendly_and_clean(tmp_path):
    with pytest.raises(FetchError) as exc:
        clone_repo(str(tmp_path / "does-not-exist"), tmp_path / "out", _allow_local=True)
    assert "Git could not fetch" in str(exc.value) or "not found" in str(exc.value)
    assert not (tmp_path / "out").exists()


# ---------- onboarding by URL, with a fake fetcher (no network) ----------

def good_q():
    return Questionnaire(purpose="Ranks job applicants' CVs for recruiters.")


def fake_fetcher(source_dir):
    def fetch(url, dest):
        shutil.copytree(source_dir, dest)
        return FetchedRepo(path=dest, url=url, commit="a" * 40)
    return fetch


def test_onboard_by_url_moves_checkout_and_records_commit(tmp_path):
    store = Store(tmp_path / "data")
    rec = onboard_application(store, name="HR", repo_url="https://github.com/ksh3001/provenix-sample-hr-cv-screener",
                              questionnaire=good_q(), frameworks=["eu_ai_act"], user="u",
                              fetcher=fake_fetcher(ROOT / "samples" / "hr_cv_screener" / "repo"),
                              samples_dir=ROOT / "samples")
    assert rec.repo_commit == "a" * 40 and rec.repo_path.endswith("checkouts\\hr") or rec.repo_path.endswith("checkouts/hr")
    assert (tmp_path / "data" / "checkouts" / "hr" / "screen.py").is_file()
    assert not list((tmp_path / "data" / "checkouts").glob("tmp-*"))
    assert store.get_app("hr").answer_key_path.endswith("hr_cv_screener\\answer_key.yaml") or \
        store.get_app("hr").answer_key_path.endswith("hr_cv_screener/answer_key.yaml")


def test_other_urls_get_no_answer_key(tmp_path):
    store = Store(tmp_path / "data")
    rec = onboard_application(store, name="Other", repo_url="https://github.com/someone/else",
                              questionnaire=good_q(), frameworks=["eu_ai_act"], user="u",
                              fetcher=fake_fetcher(ROOT / "samples" / "support_chatbot" / "repo"),
                              samples_dir=ROOT / "samples")
    assert rec.answer_key_path == ""


def test_failed_fetch_leaves_nothing_behind(tmp_path):
    store = Store(tmp_path / "data")

    def failing(url, dest):
        raise FetchError("Repository not found, or it is private. Only public repositories are supported.")

    with pytest.raises(ValueError, match="private"):
        onboard_application(store, name="X", repo_url="https://github.com/a/b", questionnaire=good_q(),
                            frameworks=["eu_ai_act"], user="u", fetcher=failing)
    assert store.list_apps() == []


def test_url_and_folder_together_rejected(tmp_path):
    with pytest.raises(ValueError, match="not both"):
        onboard_application(Store(tmp_path), name="X", repo_path=str(tmp_path), repo_url="https://github.com/a/b",
                            questionnaire=good_q(), frameworks=["eu_ai_act"], user="u")


def test_bad_url_never_reaches_fetcher(tmp_path):
    def boom(url, dest):
        raise AssertionError("fetcher must not be called")

    with pytest.raises(ValueError, match="https"):
        onboard_application(Store(tmp_path), name="X", repo_url="file:///etc", questionnaire=good_q(),
                            frameworks=["eu_ai_act"], user="u", fetcher=boom)


def test_sample_keys_have_repo_urls():
    assert find_answer_key(ROOT / "samples", "https://github.com/ksh3001/provenix-sample-support-chatbot.git")
    assert find_answer_key(ROOT / "samples", "https://github.com/x/y") is None
