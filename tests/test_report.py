import re

from core.agreement import compute_agreement
from core.answer_key import load_answer_key
from core.config import ROOT
from core.findings import Citation, Finding, FindingsFile
from core.models import AppRecord, PackInfo
from core.report import build_report_html
from core.review import ReviewFile, record_decision
from core.tiers import load_classifier
from core.questionnaire import Questionnaire

PACK = PackInfo(id="eu_ai_act", name="EU AI Act", version="0.1-draft", source="Regulation (EU) 2024/1689", status="draft")
APP = AppRecord(app_id="hr", name="HR <Screener>", repo_url="https://github.com/o/r", repo_commit="a" * 40)
KEY = load_answer_key(ROOT / "samples" / "hr_cv_screener" / "answer_key.yaml")
Q = Questionnaire.model_validate_json((ROOT / "samples" / "hr_cv_screener" / "questionnaire.json").read_text(encoding="utf-8"))
TIER = load_classifier(ROOT / "control_packs" / "eu_ai_act")(Q)


def findings(mode="live"):
    c14 = [Citation(area="repo", path="screen.py", start=45, end=46, excerpt='x = "<script>alert(1)</script>"\nsend()',
                    excerpt_sha256="a" * 64, file_sha256="b" * 64),
           Citation(area="docs", path="oversight_policy.md", start=8, end=8, excerpt="A human recruiter reviews every rejection",
                    excerpt_sha256="c" * 64, file_sha256="d" * 64, role="contradicted_claim")]
    fs = [Finding(control_id="eu-art-14", article="Article 14", title="Human oversight", status="not_met",
                  rationale="Rejections are <b>automatic</b>.", citations=c14, verification="verified"),
          Finding(control_id="eu-art-12", article="Article 12", title="Logging", status="met", rationale="Logged."),
          Finding(control_id="eu-art-9", article="Article 9", title="Risk management", status="insufficient_evidence"),
          Finding(control_id="eu-art-50-1", article="Article 50(1)", title="Disclosure", status="not_applicable",
                  source="rule", rationale="Applies only when the system interacts directly with people.")]
    return FindingsFile(app_id="hr", framework="eu_ai_act", findings=fs, finished_at="2026-01-02T00:00:00+00:00",
                        llm_mode=mode, repo_commit="a" * 40)


def render(fs, review=None, with_key=True):
    agreement = compute_agreement(fs, KEY, TIER.tier) if with_key else None
    return build_report_html(app=APP, pack=PACK, tier=TIER, findings=fs, review=review, agreement=agreement,
                             coverage_partial=False)


def test_report_contains_the_key_sections():
    html = render(findings())
    for text in ("High risk", "Annex III point 4(a)", "Compliance score", "Top gaps", "Article 14",
                 "Document claim not backed by the code", "Agreement with the expert answer key", "Draft control pack",
                 "Draft answer key", "not an official EU rating", "not legal advice"):
        assert text in html, text
    assert re.search(r"<div class=\"n\">45</div>", html) and "sha256 aaaaaaaaaaaa" in html


def test_everything_from_the_app_is_html_escaped():
    html = render(findings())
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "HR &lt;Screener&gt;" in html and "<b>automatic</b>" not in html


def test_report_is_self_contained():
    html = render(findings())
    assert not re.search(r"(src|href)=[\"']https?://", html) and "<link " not in html and "<script" not in html


def test_fake_mode_report_is_clearly_marked():
    assert "Placeholder results" in render(findings("fake")) and "Placeholder results" not in render(findings("live"))


def test_reviewer_changes_show_in_report_and_score():
    fs = findings()
    review = ReviewFile(app_id="hr", framework="eu_ai_act")
    record_decision(review, fs.findings[0], decision="overridden", final_status="partial",
                    note="A human does review, see runbook.", reviewer="Asha", run=fs.finished_at)
    html = render(fs, review)
    assert "Changed by reviewer" in html and "A human does review, see runbook." in html
    assert "reviewed by Asha" in html and "Tool alone:" in html


def test_report_without_answer_key_has_no_agreement_section():
    html = render(findings(), with_key=False)
    assert "Agreement with" not in html
