import pytest

from core.answer_key import load_answer_key
from core.config import ROOT
from core.controls import load_controls
from core.questionnaire import Questionnaire
from core.samples import install_samples
from core.store import Store

SAMPLES = ROOT / "samples"
CONTROLS = [c.id for c in load_controls(ROOT / "control_packs" / "eu_ai_act")]
APPS = ["hr_cv_screener", "support_chatbot"]


@pytest.mark.parametrize("app", APPS)
def test_key_covers_every_control(app):
    key = load_answer_key(SAMPLES / app / "answer_key.yaml")
    assert set(key.controls) == set(CONTROLS)


@pytest.mark.parametrize("app", APPS)
def test_evidence_matches_the_files(app):
    """Every cited line range exists and really contains the stated text."""
    key = load_answer_key(SAMPLES / app / "answer_key.yaml")
    for cid, control in key.controls.items():
        for ev in control.evidence:
            path = SAMPLES / app / ev.area / ev.file
            lines = path.read_text(encoding="utf-8").splitlines()
            start, end = ev.lines
            assert 1 <= start <= end <= len(lines), (cid, ev.file)
            assert ev.contains in "\n".join(lines[start - 1:end]), (cid, ev.file, ev.lines)


@pytest.mark.parametrize("app", APPS)
def test_questionnaire_valid_and_apps_are_small(app):
    q = Questionnaire.model_validate_json((SAMPLES / app / "questionnaire.json").read_text(encoding="utf-8"))
    assert q.problems() == []
    total = sum(len(p.read_text(encoding="utf-8").splitlines())
                for p in (SAMPLES / app).rglob("*") if p.is_file() and p.suffix in {".py", ".md", ".yaml"}
                and p.name != "answer_key.yaml")
    assert total < 500


def test_expected_results_from_the_plan():
    a = load_answer_key(SAMPLES / "hr_cv_screener" / "answer_key.yaml")
    assert a.expected_tier == "high"
    assert {k: a.controls[k].status for k in ("eu-art-12", "eu-art-11", "eu-art-14", "eu-art-9", "eu-art-10")} == {
        "eu-art-12": "met", "eu-art-11": "partial", "eu-art-14": "not_met",
        "eu-art-9": "insufficient_evidence", "eu-art-10": "partial"}
    assert a.trap_cases[0].control == "eu-art-14"
    b = load_answer_key(SAMPLES / "support_chatbot" / "answer_key.yaml")
    assert b.expected_tier == "limited" and b.controls["eu-art-50-1"].status == "met"
    assert all(b.controls[f"eu-art-{n}"].status == "not_applicable" for n in range(9, 16))


def test_answer_key_not_inside_assessed_folders():
    for app in APPS:
        assert not list((SAMPLES / app / "repo").rglob("answer_key*"))
        assert not list((SAMPLES / app / "docs").rglob("answer_key*"))


def test_install_samples_is_idempotent(tmp_path):
    store = Store(tmp_path)
    assert len(install_samples(store, SAMPLES, ["eu_ai_act"], "asha")) == 2
    assert install_samples(store, SAMPLES, ["eu_ai_act"], "asha") == []
    assert len(store.list_apps()) == 2
