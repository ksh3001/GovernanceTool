from core.agreement import compute_agreement
from core.answer_key import load_answer_key
from core.config import ROOT
from core.findings import Citation, Finding, FindingsFile

KEY = load_answer_key(ROOT / "samples" / "hr_cv_screener" / "answer_key.yaml")
CONTROLS = list(KEY.controls)


def cite(path, start, end, role="supports"):
    return Citation(area="repo", path=path, start=start, end=end, excerpt="x", excerpt_sha256="0" * 64,
                    file_sha256="1" * 64, role=role)


def findings(overrides=None, citations=None):
    """Findings that exactly match the key, with specific controls changed."""
    overrides, citations = overrides or {}, citations or {}
    out = []
    for cid, k in KEY.controls.items():
        out.append(Finding(control_id=cid, article=cid, title=cid, status=overrides.get(cid, k.status),
                           citations=citations.get(cid, []),
                           source="rule" if k.status == "not_applicable" else "model"))
    return FindingsFile(app_id="a", framework="eu_ai_act", findings=out)


def test_perfect_match():
    a = compute_agreement(findings(), KEY, "high")
    assert (a.agreed, a.total) == (9, 9) and a.tier_match
    assert (a.assessed_agreed, a.assessed_total) == (7, 7)  # the two N/A controls are decided by rule


def test_disagreements_are_counted_per_control():
    a = compute_agreement(findings({"eu-art-12": "partial", "eu-art-14": "met"}), KEY, "high")
    assert (a.agreed, a.assessed_agreed, a.assessed_total) == (7, 5, 7)
    assert {c.control_id for c in a.controls if not c.match} == {"eu-art-12", "eu-art-14"}


def test_tier_mismatch():
    assert not compute_agreement(findings(), KEY, "limited").tier_match


def test_evidence_match_by_file_name_and_overlapping_lines():
    good = cite("audit.py", 12, 14)  # inside the expert's 10-20
    a = compute_agreement(findings(citations={"eu-art-12": [good]}), KEY, "high")
    assert next(c for c in a.controls if c.control_id == "eu-art-12").evidence_match is True
    off = compute_agreement(findings(citations={"eu-art-12": [cite("audit.py", 30, 34)]}), KEY, "high")
    assert next(c for c in off.controls if c.control_id == "eu-art-12").evidence_match is False
    none = compute_agreement(findings(), KEY, "high")
    assert next(c for c in none.controls if c.control_id == "eu-art-12").evidence_match is False
    assert next(c for c in none.controls if c.control_id == "eu-art-9").evidence_match is None  # expert lists none


def test_documents_in_a_cloned_repo_still_match_by_name():
    c = cite("docs/oversight_policy.md", 8, 8, "contradicted_claim")
    a = compute_agreement(findings(citations={"eu-art-14": [cite("screen.py", 45, 52), c]}), KEY, "high")
    assert next(c for c in a.controls if c.control_id == "eu-art-14").evidence_match is True
    assert a.traps[0].detected


def test_trap_not_detected_without_the_document_claim_citation():
    a = compute_agreement(findings(citations={"eu-art-14": [cite("screen.py", 45, 52)]}), KEY, "high")
    assert a.traps[0].control_id == "eu-art-14" and not a.traps[0].detected


def test_a_draft_key_is_flagged_unconfirmed():
    assert not compute_agreement(findings(), KEY, "high").confirmed_by_expert
