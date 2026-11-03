"""End-to-end UI flow with seeded findings: dashboard, review, override, dashboard updates."""
import json
import os

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.assess import run_assessment
from core.config import ROOT, Settings
from core.controls import load_controls
from core.findings import FindingsFile, findings_path
from core.ingest import ingest
from core.llm import LLMClient
from core.questionnaire import Questionnaire
from core.review import ReviewFile, review_path
from core.samples import install_samples
from core.store import Store
from core.tiers import control_applicability, load_classifier

PACK = ROOT / "control_packs" / "eu_ai_act"
SAMPLES = ROOT / "samples"


def scripted(system, prompt):
    if "VERIFIER" in system:
        return json.dumps({"verdict": "supported", "reason": "Supported.", "citations": [{"index": 0, "supports": True}]})
    if "Article 12 " in prompt.split("\n")[0]:
        return json.dumps({"status": "met", "rationale": "Every decision is logged.",
                           "citations": [{"file": "repo/audit.py", "start_line": 10, "end_line": 20}]})
    if "Article 14 " in prompt.split("\n")[0]:
        return json.dumps({"status": "not_met", "rationale": "Rejections are automatic.", "citations": [
            {"file": "repo/screen.py", "start_line": 45, "end_line": 52},
            {"file": "docs/oversight_policy.md", "start_line": 8, "end_line": 8, "role": "contradicted_claim"}]})
    return json.dumps({"status": "insufficient_evidence", "rationale": "Not enough.", "citations": []})


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVENIX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PROVENIX_LLM_MODE", "fake")
    st.cache_resource.clear()
    store = Store(tmp_path)
    app = next(a for a in install_samples(store, SAMPLES, ["eu_ai_act"], "seed") if a.name == "HR CV Screener")
    q = Questionnaire.model_validate_json((SAMPLES / "hr_cv_screener" / "questionnaire.json").read_text(encoding="utf-8"))
    tier = load_classifier(PACK)(q)
    controls = load_controls(PACK)
    settings = Settings(llm_mode="fake", demo_password="", azure_endpoint="", azure_api_key="", azure_deployment="",
                        azure_api_version="x", data_dir=tmp_path, packs_dir=PACK.parent)
    result = run_assessment(app_id=app.app_id, framework="eu_ai_act", controls=controls,
                            applicability=control_applicability(controls, tier.tier, q), q=q, tier=tier,
                            ingested=ingest(app.repo_path, app.docs_path), llm=LLMClient(settings, fake_handler=scripted))
    store.save(app.app_id, findings_path("eu_ai_act"), result)
    return store, app


def open_app():
    at = AppTest.from_file(str(ROOT / "main.py"), default_timeout=60).run()
    at.text_input[0].set_value("Asha")
    at.button[0].click(); at.run()
    at.checkbox[0].check(); at.run()
    next(b for b in at.button if b.label == "Continue").click(); at.run()
    next(b for b in at.button if b.label == "Open application").click(); at.run()
    assert not at.exception, at.exception
    return at


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def test_dashboard_shows_tier_score_and_gaps(seeded):
    at = open_app()
    assert "High risk" in " ".join(m.value for m in at.markdown)
    # 7 applicable: 1 met, 1 not met, 5 insufficient  ->  1/7 = 14%
    assert metric(at, "Compliance score") == "14%" and metric(at, "Reviewed").startswith("0 of 9")
    gap_buttons = {b.key for b in at.button if b.key and b.key.startswith("gap_")}
    assert "gap_eu_ai_act_eu-art-14" in gap_buttons and "gap_eu_ai_act_eu-art-9" in gap_buttons
    assert "gap_eu_ai_act_eu-art-12" not in gap_buttons  # a met control is not a gap
    assert "not an official EU rating" in " ".join(c.value for c in at.caption)


def test_review_override_updates_dashboard_and_saves_audit_trail(seeded):
    store, app = seeded
    at = open_app()
    at.radio(key="section_eu_ai_act").set_value("Review").run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert 'class="cv"' in html and "reviews every rejection" in html  # citation viewer shows the trap claim

    # an override without a note is refused and saves nothing
    at.radio(key="act_eu_ai_act_eu-art-14").set_value("Override")
    at.selectbox(key="new_eu_ai_act_eu-art-14").set_value("partial")
    next(b for b in at.button if b.key == "save_eu_ai_act_eu-art-14").click(); at.run()
    assert any("note is required" in e.value for e in at.error)
    assert store.load(app.app_id, review_path("eu_ai_act"), ReviewFile) is None

    at.text_area(key="note_eu_ai_act_eu-art-14").set_value("A human does review in practice, see HR runbook.")
    next(b for b in at.button if b.key == "save_eu_ai_act_eu-art-14").click(); at.run()
    saved = store.load(app.app_id, review_path("eu_ai_act"), ReviewFile)
    d = saved.decisions["eu-art-14"]
    assert (d.decision, d.tool_status, d.final_status, d.reviewer) == ("overridden", "not_met", "partial", "Asha")
    assert store.load(app.app_id, findings_path("eu_ai_act"), FindingsFile).by_control()["eu-art-14"].status == "not_met"

    at.radio(key="section_eu_ai_act").set_value("Dashboard").run()
    assert metric(at, "Reviewed").startswith("1 of 9")
    assert metric(at, "Compliance score") == "21%"  # (1 met + 0.5 partial) / 7
    assert "tool alone: 14%" in next(m.delta for m in at.metric if m.label == "Compliance score")


def test_confirm_decision(seeded):
    store, app = seeded
    at = open_app()
    at.radio(key="section_eu_ai_act").set_value("Review").run()
    next(b for b in at.button if b.key == "save_eu_ai_act_eu-art-12").click(); at.run()  # default action is Confirm
    d = store.load(app.app_id, review_path("eu_ai_act"), ReviewFile).decisions["eu-art-12"]
    assert (d.decision, d.final_status) == ("confirmed", "met")


def test_gap_open_button_jumps_to_review(seeded):
    at = open_app()
    next(b for b in at.button if b.key == "gap_eu_ai_act_eu-art-14").click(); at.run()
    assert at.radio(key="section_eu_ai_act").value == "Review"


def test_dashboard_shows_agreement_with_draft_key_warning(seeded):
    at = open_app()
    text = " ".join(w.value for w in at.warning)
    assert "Draft answer key" in text
    assert next(m.value for m in at.metric if m.label == "Controls matched") == "3 of 7"  # Art. 9, 12 and 14 match the key
    assert any("Trap case (eu-art-14): detected" in s.value for s in at.success)


def test_report_section_offers_download_and_includes_review(seeded):
    store, app = seeded
    at = open_app()
    at.radio(key="section_eu_ai_act").set_value("Report").run()
    assert not at.exception, at.exception
    downloads = at.get("download_button")
    assert len(downloads) == 1 and "Download report" in downloads[0].proto.label


def test_home_card_shows_assessment_progress(seeded):
    store, app = seeded
    at = AppTest.from_file(str(ROOT / "main.py"), default_timeout=60).run()
    at.text_input[0].set_value("Asha"); at.button[0].click(); at.run()
    at.checkbox[0].check(); at.run()
    next(b for b in at.button if b.label == "Continue").click(); at.run()
    captions = " ".join(c.value for c in at.caption)
    assert "Assessed · compliance score 14%" in captions and "Not assessed yet" in captions
