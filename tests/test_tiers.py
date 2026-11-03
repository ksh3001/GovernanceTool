import pytest

from core.answer_key import load_answer_key
from core.config import ROOT
from core.controls import load_controls
from core.questionnaire import Questionnaire
from core.tiers import control_applicability, load_classifier

PACK = ROOT / "control_packs" / "eu_ai_act"
SAMPLES = ROOT / "samples"
classify = load_classifier(PACK)
CONTROLS = load_controls(PACK)


def q(**kw):
    kw.setdefault("purpose", "A system that does something useful for people.")
    return Questionnaire(**kw)


def sample_q(app):
    return Questionnaire.model_validate_json((SAMPLES / app / "questionnaire.json").read_text(encoding="utf-8"))


def test_pack_without_rules_has_no_classifier(tmp_path):
    assert load_classifier(tmp_path) is None


def test_app_a_is_high_risk_annex_iii_4a():
    r = classify(sample_q("hr_cv_screener"))
    assert (r.tier, r.rule_id, r.legal_basis) == ("high", "art6_2", "Annex III point 4(a)")
    assert "employment" in r.reason.lower()


def test_app_b_is_limited_risk_art_50():
    r = classify(sample_q("support_chatbot"))
    assert (r.tier, r.rule_id, r.legal_basis) == ("limited", "art50", "Article 50")


def test_employment_not_about_recruitment_is_4b():
    r = classify(q(annex_iii_area="employment", purpose="Allocates daily tasks to warehouse staff."))
    assert r.tier == "high" and r.legal_basis == "Annex III point 4(b)"


def test_prohibited_beats_everything_else():
    r = classify(q(prohibited_practices=["social_scoring"], annex_iii_area="employment"))
    assert (r.tier, r.rule_id) == ("prohibited", "art5")


def test_out_of_scope_when_not_in_eu():
    assert classify(q(eu_market=False, prohibited_practices=["social_scoring"])).tier == "out_of_scope"


def test_safety_component_is_high():
    assert classify(q(safety_component_annex_i=True)).rule_id == "art6_1"


def test_art_6_3_exemption_only_without_individual_impact():
    exempt = classify(q(annex_iii_area="education", narrow_procedural_task=True, affects_individuals=False))
    assert (exempt.tier, exempt.rule_id) == ("minimal", "art6_3")
    not_exempt = classify(q(annex_iii_area="education", narrow_procedural_task=True, affects_individuals=True))
    assert not_exempt.tier == "high"


def test_exempt_system_that_chats_is_limited():
    r = classify(q(annex_iii_area="education", narrow_procedural_task=True, interacts_with_people=True))
    assert r.tier == "limited"


def test_synthetic_content_is_limited_and_default_is_minimal():
    assert classify(q(generates_synthetic_content=True)).tier == "limited"
    assert classify(q()).tier == "minimal"


def test_steps_trace_shows_every_rule_checked_in_order():
    r = classify(sample_q("hr_cv_screener"))
    assert [s.rule_id for s in r.steps] == ["scope", "art5", "art6_1", "art6_2", "art6_3"]
    assert [s.matched for s in r.steps][:3] == [True, False, False]


@pytest.mark.parametrize("app", ["hr_cv_screener", "support_chatbot"])
def test_applicability_matches_answer_key(app):
    """Controls the key marks not_applicable are exactly those the code marks not applicable."""
    questionnaire = sample_q(app)
    tier = classify(questionnaire).tier
    key = load_answer_key(SAMPLES / app / "answer_key.yaml")
    assert tier == key.expected_tier
    for item in control_applicability(CONTROLS, tier, questionnaire):
        expected_na = key.controls[item.control_id].status == "not_applicable"
        assert item.applies is not expected_na, item.control_id


def test_prohibited_system_has_no_applicable_controls():
    items = control_applicability(CONTROLS, "prohibited", q())
    assert not any(i.applies for i in items) and "Not assessed" in items[0].reason
