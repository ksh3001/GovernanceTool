"""Rule scoping: role-aware applicability, reviewer changes, custom rules, and the third sample app."""
import json
import re

import pytest

from core.agreement import compute_agreement
from core.answer_key import load_answer_key
from core.assess import run_assessment
from core.config import ROOT, Settings
from core.controls import load_controls
from core.ingest import ingest
from core.llm import LLMClient
from core.onboarding import onboard_application
from core.questionnaire import Questionnaire
from core.report import build_report_html
from core.models import AppRecord, PackInfo
from core.samples import install_samples
from core.scope import (add_custom_rule, effective_scope, exclude_rule, finalise, include_rule, new_scope, preview,
                        reopen, revert_rule, scoped_rules, summarise_scope)
from core.store import Store
from core.tiers import control_applicability, load_classifier

PACK = ROOT / "control_packs" / "eu_ai_act"
SAMPLES = ROOT / "samples"
CONTROLS = load_controls(PACK)


def applies(q: Questionnaire) -> set[str]:
    tier = load_classifier(PACK)(q)
    return {a.control_id for a in control_applicability(CONTROLS, tier.tier, q) if a.applies}


def hr(**kw) -> Questionnaire:
    base = dict(purpose="Scores job applicants' CVs and shortlists candidates.", annex_iii_area="employment",
                affects_individuals=True, autonomy="fully_automated")
    return Questionnaire(**{**base, **kw})


HIGH_PROVIDER = {"eu-art-4", "eu-art-9", "eu-art-10", "eu-art-11", "eu-art-12", "eu-art-13", "eu-art-14",
                 "eu-art-15", "eu-art-17", "eu-art-43", "eu-art-49", "eu-art-72", "eu-art-73"}


# ---------- applicability from the questionnaire ----------

def test_role_decides_provider_and_deployer_duties():
    assert applies(hr(role="provider")) == HIGH_PROVIDER
    assert applies(hr(role="deployer")) == {"eu-art-4", "eu-art-26"}
    assert applies(hr(role="provider_and_deployer")) == HIGH_PROVIDER | {"eu-art-26"}


def test_fria_only_for_public_bodies_and_credit_or_insurance():
    assert "eu-art-27" not in applies(hr(role="deployer"))
    assert "eu-art-27" in applies(hr(role="deployer", public_body_or_service=True))
    credit = Questionnaire(purpose="Scores loan applicants' creditworthiness.", role="deployer",
                           credit_or_insurance=True, affects_individuals=True)
    tier = load_classifier(PACK)(credit)
    assert tier.tier == "high" and tier.legal_basis == "Annex III point 5(b)"  # credit implies Annex III 5 by itself
    assert "eu-art-27" in applies(credit)


def test_transparency_and_gpai_flags():
    assert applies(Questionnaire(purpose="Generates marketing videos with avatars.", role="deployer",
                                 deep_fake=True)) == {"eu-art-4", "eu-art-50-4"}
    assert applies(Questionnaire(purpose="Detects shopper emotions from cameras.", role="deployer",
                                 emotion_or_biometric_categorisation=True)) == {"eu-art-4", "eu-art-50-3"}
    gpai = applies(Questionnaire(purpose="Foundation model offered to other companies.", gpai_model=True,
                                 gpai_systemic_risk=True))
    assert {"eu-art-53", "eu-art-55", "eu-art-4"} <= gpai


def test_minimal_risk_system_still_has_ai_literacy():
    assert applies(Questionnaire(purpose="Suggests internal wiki tags for documents.")) == {"eu-art-4"}


def test_reasons_explain_both_ways():
    q = hr(role="provider")
    by_id = {a.control_id: a for a in control_applicability(CONTROLS, "high", q)}
    assert by_id["eu-art-14"].reason == "Applies: high-risk system; you are the provider."
    assert "duty of the deployer" in by_id["eu-art-26"].reason
    assert "interacts directly with people" in by_id["eu-art-50-1"].reason


def test_preview_matches_the_scope():
    p = preview(hr(role="provider"), PACK)
    assert p.tier == "high" and len(p.rules) == len(HIGH_PROVIDER) and p.total == len(CONTROLS)


# ---------- reviewer changes ----------

def proposed(q):
    return control_applicability(CONTROLS, load_classifier(PACK)(q).tier, q)


def test_remove_add_back_and_undo_with_reasons():
    q, scope = hr(role="provider"), new_scope("a", "eu_ai_act")
    with pytest.raises(ValueError, match="reason"):
        exclude_rule(scope, "eu-art-49", "", "asha")
    exclude_rule(scope, "eu-art-49", "Registration is handled by the group regulatory team", "asha")
    include_rule(scope, "eu-art-26", "We also run the tool ourselves", "asha")
    rules = {r.control.id: r for r in scoped_rules(CONTROLS, proposed(q), scope)}
    assert not rules["eu-art-49"].applies and rules["eu-art-49"].change == "removed"
    assert rules["eu-art-26"].applies and rules["eu-art-26"].change == "added"
    assert "group regulatory team" in rules["eu-art-49"].reason
    revert_rule(scope, "eu-art-49", "asha")
    assert {r.control.id: r for r in scoped_rules(CONTROLS, proposed(q), scope)}["eu-art-49"].applies
    assert [e.action for e in scope.history] == ["excluded", "included", "reverted"]


def test_custom_rule_gets_id_and_keywords():
    scope = new_scope("a", "eu_ai_act")
    rule = add_custom_rule(scope, reference="EY AI Policy 4.2", title="Prompt logging",
                           requirement="Every prompt and response is stored with a timestamp for 12 months.",
                           expected_evidence="code", by="asha")
    assert rule.id == "custom-prompt-logging" and "prompt" in rule.search_terms and "every" not in rule.search_terms
    again = add_custom_rule(scope, reference="", title="Prompt logging", requirement="x" * 25,
                            expected_evidence="both", search_terms="foo, bar", by="asha")
    assert again.id == "custom-prompt-logging-2" and again.search_terms == ["foo", "bar"]
    with pytest.raises(ValueError, match="what must be true"):
        add_custom_rule(scope, reference="", title="Short", requirement="too short", expected_evidence="both", by="a")


def test_finalise_locks_and_reopen_unlocks():
    q, scope = hr(role="provider"), new_scope("a", "eu_ai_act")
    finalise(scope, scoped_rules(CONTROLS, proposed(q), scope), "asha")
    assert scope.finalised and scope.finalised_by == "asha" and "13 rules in scope" in scope.history[-1].detail
    with pytest.raises(ValueError, match="finalised"):
        exclude_rule(scope, "eu-art-9", "not needed here", "asha")
    reopen(scope, "asha")
    assert not scope.finalised


def test_cannot_finalise_an_empty_scope():
    q, scope = Questionnaire(purpose="Suggests internal wiki tags."), new_scope("a", "eu_ai_act")
    exclude_rule(scope, "eu-art-4", "Covered by the company-wide training", "asha")
    with pytest.raises(ValueError, match="No rule is in scope"):
        finalise(scope, scoped_rules(CONTROLS, proposed(q), scope), "asha")


# ---------- the assessment uses the finalised scope ----------

def settings(tmp_path, mode="fake"):
    return Settings(llm_mode=mode, demo_password="", azure_endpoint="", azure_api_key="", azure_deployment="",
                    azure_api_version="x", data_dir=tmp_path, packs_dir=PACK.parent)


class KeyModel:
    """Fake model that answers from an answer key, and approves every citation in the verifier."""

    def __init__(self, key, custom_reply=None):
        self.key, self.custom_reply, self.calls = key, custom_reply, []
        self.by_article = {}
        for c in CONTROLS:
            self.by_article.setdefault(c.article, c.id)

    def __call__(self, system, prompt):
        if "VERIFIER" in system:
            return json.dumps({"verdict": "supported", "reason": "ok", "citations": []})
        article = re.search(r"CONTROL: (.+?) - ", prompt).group(1)
        self.calls.append(article)
        cid = self.by_article.get(article)
        if cid is None or cid not in self.key.controls:
            return json.dumps(self.custom_reply or {"status": "insufficient_evidence", "rationale": "x"})
        k = self.key.controls[cid]
        return json.dumps({"status": k.status, "rationale": k.note, "citations": [
            {"file": f"{e.area}/{e.file}", "start_line": e.lines[0], "end_line": e.lines[1], "role": e.role}
            for e in k.evidence]})


def run_sample(tmp_path, app, scope=None, custom_reply=None, mode="fake"):
    folder = SAMPLES / app
    key = load_answer_key(folder / "answer_key.yaml")
    q = Questionnaire.model_validate_json((folder / "questionnaire.json").read_text(encoding="utf-8"))
    tier = load_classifier(PACK)(q)
    controls, applic = effective_scope(CONTROLS, control_applicability(CONTROLS, tier.tier, q), scope)
    model = KeyModel(key, custom_reply)
    llm = LLMClient(settings(tmp_path, mode), fake_handler=model)
    out = run_assessment(app_id=app, framework="eu_ai_act", controls=controls, applicability=applic, q=q, tier=tier,
                         ingested=ingest(folder / "repo", folder / "docs"), llm=llm)
    return out, key, tier, model


def test_loan_sample_matches_its_key_and_catches_the_postcode_trap(tmp_path):
    findings, key, tier, _ = run_sample(tmp_path, "loan_assistant")
    assert tier.tier == "high" and tier.legal_basis == "Annex III point 5(b)"
    a = compute_agreement(findings, key, tier.tier)
    assert (a.agreed, a.total, a.assessed_total) == (21, 21, 16) and a.tier_match
    assert a.traps and all(t.detected for t in a.traps)
    art10 = findings.by_control()["eu-art-10"]
    assert any(c.role == "contradicted_claim" and "Postcode" in c.excerpt for c in art10.citations)


def test_removed_added_and_custom_rules_flow_through_the_run(tmp_path):
    scope = new_scope("hr", "eu_ai_act")
    exclude_rule(scope, "eu-art-49", "Registration handled by group regulatory team", "asha")
    include_rule(scope, "eu-art-26", "We also deploy it in our own HR team", "asha")
    add_custom_rule(scope, reference="EY AI Policy 4.2", title="Decision logging",
                    requirement="Every screening decision is logged with a timestamp and model version.",
                    expected_evidence="code", by="asha")
    reply = {"status": "met", "rationale": "Logged.", "citations": [{"file": "repo/audit.py", "start_line": 10, "end_line": 20}]}
    findings, key, tier, model = run_sample(tmp_path, "hr_cv_screener", scope, custom_reply=reply)
    by_id = findings.by_control()
    assert by_id["eu-art-49"].status == "not_applicable" and by_id["eu-art-49"].source == "user"
    assert by_id["eu-art-49"].scope_change == "removed" and "Article 49" not in model.calls
    assert by_id["eu-art-26"].scope_change == "added" and "Article 26" in model.calls
    custom = by_id["custom-decision-logging"]
    assert custom.scope_change == "custom" and custom.status == "met" and custom.citations[0].path == "audit.py"
    a = compute_agreement(findings, key, tier.tier)
    assert {"eu-art-49", "eu-art-26", "custom-decision-logging"}.isdisjoint({c.control_id for c in a.controls})


def test_custom_rule_without_a_recording_does_not_stop_a_replay_run(tmp_path):
    from core.assess import assess_control
    from core.scope import custom_control
    scope = new_scope("hr", "eu_ai_act")
    rule = add_custom_rule(scope, reference="Policy", title="Prompt logging",
                           requirement="Every prompt is stored with a timestamp for 12 months.",
                           expected_evidence="code", by="asha")
    folder = SAMPLES / "hr_cv_screener"
    q = Questionnaire.model_validate_json((folder / "questionnaire.json").read_text(encoding="utf-8"))
    replay = LLMClient(Settings(llm_mode="replay", demo_password="", azure_endpoint="", azure_api_key="",
                                azure_deployment="", azure_api_version="x", data_dir=tmp_path,
                                packs_dir=PACK.parent, replay_cache=tmp_path / "empty.jsonl"))
    f = assess_control(custom_control(rule), q, None, ingest(folder / "repo", folder / "docs"), replay)
    assert f.status == "insufficient_evidence" and "custom rule" in f.flags[0]


def test_report_shows_the_scope_and_every_change(tmp_path):
    scope = new_scope("hr", "eu_ai_act")
    exclude_rule(scope, "eu-art-49", "Registration handled by group regulatory team", "asha")
    q = Questionnaire.model_validate_json((SAMPLES / "hr_cv_screener" / "questionnaire.json").read_text())
    rules = scoped_rules(CONTROLS, proposed(q), scope)
    finalise(scope, rules, "asha")
    findings, key, tier, _ = run_sample(tmp_path, "hr_cv_screener", scope)
    html = build_report_html(app=AppRecord(app_id="hr", name="HR CV Screener"),
                             pack=PackInfo(id="eu_ai_act", name="EU AI Act", version="0.1"), tier=tier,
                             findings=findings, review=None, agreement=None, coverage_partial=False,
                             controls=CONTROLS, scope_rules=rules, scope=scope)
    assert "Assessment scope" in html and "12 rules were assessed" in html
    assert "group regulatory team" in html and "Removed from scope" in html and "Scope finalised by asha" in html
    s = summarise_scope(rules)
    assert (s.in_scope, s.proposed, s.removed) == (12, 13, 1)


# ---------- samples and onboarding ----------

def test_loan_sample_is_kept_out_of_load_sample_apps_but_keyed_when_onboarded(tmp_path):
    store = Store(tmp_path)
    names = {a.name for a in install_samples(store, SAMPLES, ["eu_ai_act"], "seed")}
    assert names == {"HR CV Screener", "Support Chatbot"}
    q = Questionnaire.model_validate_json((SAMPLES / "loan_assistant" / "questionnaire.json").read_text())
    record = onboard_application(store, name="Loan Pre-Approval Assistant",
                                 repo_path=str(SAMPLES / "loan_assistant" / "repo"),
                                 docs_path=str(SAMPLES / "loan_assistant" / "docs"), questionnaire=q,
                                 frameworks=["eu_ai_act"], user="asha", samples_dir=SAMPLES)
    assert record.answer_key_path.endswith("loan_assistant/answer_key.yaml")


def test_old_questionnaires_without_new_answers_still_load():
    q = Questionnaire.model_validate({"purpose": "An older saved questionnaire.", "role": "deployer"})
    assert not q.credit_or_insurance and not q.gpai_model and q.is_deployer and not q.is_provider
