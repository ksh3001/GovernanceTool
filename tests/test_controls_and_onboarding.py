import pytest

from core.config import ROOT
from core.controls import load_controls
from core.onboarding import load_questionnaire, onboard_application
from core.questionnaire import Questionnaire
from core.store import Store

PACK = ROOT / "control_packs" / "eu_ai_act"


def test_pack_has_8_to_10_complete_controls():
    controls = load_controls(PACK)
    assert 8 <= len(controls) <= 10
    for c in controls:
        assert c.article and c.quote and c.paraphrase and c.search_terms
        assert c.source_url.startswith("https://eur-lex.europa.eu/")
        assert c.applies_to_tiers


def test_high_risk_articles_only_apply_to_high_tier():
    by_id = {c.id: c for c in load_controls(PACK)}
    for n in (9, 10, 11, 12, 13, 14, 15):
        assert by_id[f"eu-art-{n}"].applies_to_tiers == ["high"]
    assert "limited" in by_id["eu-art-50-1"].applies_to_tiers


def good_q(**kw):
    return Questionnaire(purpose="Ranks job applicants' CVs for recruiters.", **kw)


def test_onboard_saves_record_and_questionnaire(tmp_path):
    store = Store(tmp_path / "data")
    repo = tmp_path / "repo"
    repo.mkdir()
    rec = onboard_application(store, name="HR Tool", repo_path=str(repo), docs_path="",
                              questionnaire=good_q(annex_iii_area="employment"),
                              frameworks=["eu_ai_act"], user="asha")
    assert rec.repo_path == str(repo.resolve()) and rec.frameworks == ["eu_ai_act"]
    assert load_questionnaire(store, rec.app_id).annex_iii_area == "employment"


def test_onboard_reports_all_problems(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ValueError) as exc:
        onboard_application(store, name="", repo_path=str(tmp_path / "missing"), docs_path="",
                            questionnaire=Questionnaire(), frameworks=[], user="x")
    msg = str(exc.value)
    for expected in ("name is required", "not a folder", "framework", "intended purpose"):
        assert expected in msg
    assert store.list_apps() == []
