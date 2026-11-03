import os
import sys

import pytest

from core.config import ROOT
from core.controls import Control, load_controls
from core.ingest import MAX_FILES, ingest
from core.questionnaire import Questionnaire
from core.relevance import estimate_tokens, score_file, select_files
from core.runplan import build_run_plan
from core.tiers import control_applicability, load_classifier

PACK = ROOT / "control_packs" / "eu_ai_act"
SAMPLES = ROOT / "samples"
CONTROLS = {c.id: c for c in load_controls(PACK)}


def write(base, rel, text="x = 1\n"):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def control(terms, evidence="both", cid="t"):
    return Control(id=cid, article="Art T", title="T", paraphrase="p", quote="q", source_url="https://x",
                   expected_evidence=evidence, applies_to_tiers=["high"], search_terms=terms)


# ---------- ingestion ----------

def test_skip_rules(tmp_path):
    write(tmp_path, "app.py")
    write(tmp_path, "node_modules/lib/index.js")
    write(tmp_path, ".git/config", "[core]")
    write(tmp_path, ".env", "KEY=secret")
    write(tmp_path, "server.pem", "-----BEGIN-----")
    write(tmp_path, "package-lock.json", "{}")
    write(tmp_path, "bundle.min.js", "a=1")
    write(tmp_path, "logo.png", "notimage")
    write(tmp_path, "big.py", "x = 1\n" * 50_000)
    (tmp_path / "blob.py").write_bytes(b"abc\x00def")
    write(tmp_path, "empty.py", "   \n")
    r = ingest(tmp_path)
    assert [f.path for f in r.files] == ["app.py"]
    reasons = {s.path: s.reason for s in r.skipped}
    assert "may contain secrets" in reasons[".env"] and "may contain secrets" in reasons["server.pem"]
    assert "lock" in reasons["package-lock.json"] and "minified" in reasons["bundle.min.js"]
    assert "not analysed" in reasons["logo.png"] and "larger" in reasons["big.py"]
    assert reasons["blob.py"] == "binary file" and reasons["empty.py"] == "empty file"
    assert not any(s.path.startswith(("node_modules", ".git")) for s in r.skipped)  # pruned, not listed


def test_records_hash_lines_and_area(tmp_path):
    repo, docs = tmp_path / "repo", tmp_path / "docs"
    write(repo, "a.py", "one\ntwo\nthree\n")
    write(docs, "card.md", "# Card\n")
    write(docs, "ignored.py", "x=1")  # code is only analysed in the repo area
    r = ingest(repo, docs)
    a = r.by_key()["repo:a.py"]
    assert (a.lines, a.kind, len(a.sha256)) == (3, "code", 64)
    assert r.by_key()["docs:card.md"].kind == "doc"
    assert "docs:ignored.py" not in r.by_key()
    assert "text" not in a.model_dump()  # file contents are never serialised


def test_pdf_without_library_is_listed_as_unreadable(tmp_path):
    (tmp_path / "policy.pdf").write_bytes(b"%PDF-1.4 fake")
    r = ingest(tmp_path, tmp_path)
    assert r.files == [] or all(f.path != "policy.pdf" for f in r.files)
    assert any(u.path == "policy.pdf" for u in r.unreadable)


def test_file_limit(tmp_path):
    for i in range(MAX_FILES + 5):
        write(tmp_path, f"f{i:04}.py")
    r = ingest(tmp_path)
    assert len(r.files) == MAX_FILES
    assert sum("file limit" in s.reason for s in r.skipped) == 5


@pytest.mark.skipif(sys.platform == "win32" and not os.environ.get("CI_SYMLINKS"), reason="symlinks need privileges on Windows")
def test_symlinks_not_followed(tmp_path):
    outside = tmp_path / "outside"
    write(outside, "secret.py")
    repo = tmp_path / "repo"
    repo.mkdir()
    os.symlink(outside / "secret.py", repo / "link.py")
    assert ingest(repo).files == []


# ---------- relevance ----------

def test_word_start_matching_avoids_noise(tmp_path):
    f = ingest(write(tmp_path, "a.py", "catalog = 1\n").parent).files[0]
    assert score_file(f, control(["log"])) == 0
    g = ingest(write(tmp_path, "b.py", "def audit_log(): pass\n").parent).by_key()["repo:b.py"]
    assert score_file(g, control(["log"])) > 0


def test_sample_app_a_small_shortcut_sends_everything():
    r = ingest(SAMPLES / "hr_cv_screener" / "repo", SAMPLES / "hr_cv_screener" / "docs")
    sel = select_files(r, CONTROLS["eu-art-12"])
    assert sel.shortcut and sel.coverage == "complete" and all(f.full for f in sel.files)
    assert len(sel.files) == len(r.files)
    assert sel.files[0].path == "audit.py"  # best match for logging ranks first


def test_relevant_file_wins_and_sees_both_code_and_doc(tmp_path):
    repo, docs = tmp_path / "repo", tmp_path / "docs"
    write(repo, "audit.py", "def log_event(): pass\n" * 40)
    for i in range(30):
        write(repo, f"util{i}.py", "value = compute()\n" * 300)
    write(docs, "oversight.md", "Human oversight: a person may override. " * 10)
    r = ingest(repo, docs)
    sel = select_files(r, control(["log", "override", "oversight"]), budget_tokens=2000)
    assert not sel.shortcut
    paths = [f.path for f in sel.files]
    assert paths[0] in ("audit.py", "oversight.md") and "audit.py" in paths and "oversight.md" in paths
    assert sel.tokens <= 2000
    assert sel.coverage == "complete"  # the irrelevant utility files score zero, so nothing relevant was cut


def test_trimmed_file_keeps_original_line_numbers(tmp_path):
    lines = [f"filler line {i}" for i in range(1, 801)]
    lines[599] = "def write_audit_log(event):  # the evidence"
    write(tmp_path, "big.py", "\n".join(lines))
    write(tmp_path, "pad.py", "filler\n" * 4000)
    r = ingest(tmp_path)
    sel = select_files(r, control(["audit"]), budget_tokens=1000)
    item = next(f for f in sel.files if f.path == "big.py")
    assert not item.full and sel.coverage == "partial" and "repo:big.py" in sel.trimmed
    seg = next(s for s in item.segments if "write_audit_log" in s.text)
    assert seg.start <= 600 <= seg.end
    assert seg.text.splitlines()[600 - seg.start].startswith("def write_audit_log")  # line 600 is where we say it is
    assert item.tokens <= 1000


def test_coverage_partial_when_relevant_files_left_out(tmp_path):
    for i in range(10):
        write(tmp_path, f"audit{i}.py", "audit log trace\n" * 400)
    r = ingest(tmp_path)
    sel = select_files(r, control(["audit", "log"]), budget_tokens=1500)
    assert sel.left_out and sel.coverage == "partial"


def test_selection_is_deterministic():
    r = ingest(SAMPLES / "hr_cv_screener" / "repo", SAMPLES / "hr_cv_screener" / "docs")
    a = select_files(r, CONTROLS["eu-art-14"], budget_tokens=900)
    b = select_files(r, CONTROLS["eu-art-14"], budget_tokens=900)
    assert a.model_dump() == b.model_dump()


def test_oversight_trap_both_files_reach_the_model_even_with_tight_budget():
    r = ingest(SAMPLES / "hr_cv_screener" / "repo", SAMPLES / "hr_cv_screener" / "docs")
    sel = select_files(r, CONTROLS["eu-art-14"], budget_tokens=600)
    paths = {f.path for f in sel.files}
    assert "screen.py" in paths and "oversight_policy.md" in paths


# ---------- run plan ----------

@pytest.mark.parametrize("app,expected_controls", [("hr_cv_screener", 7), ("support_chatbot", 1)])
def test_run_plan_for_samples(app, expected_controls):
    q = Questionnaire.model_validate_json((SAMPLES / app / "questionnaire.json").read_text(encoding="utf-8"))
    tier = load_classifier(PACK)(q).tier
    r = ingest(SAMPLES / app / "repo", SAMPLES / app / "docs")
    plan = build_run_plan(r, list(CONTROLS.values()), control_applicability(list(CONTROLS.values()), tier, q))
    assert sum(c.applies for c in plan.controls) == expected_controls
    assert plan.coverage == "complete" and plan.files_used == plan.files_found == len(r.files)
    assert 0 < plan.estimated_tokens < 40_000
    assert all(c.selection is None for c in plan.controls if not c.applies)
