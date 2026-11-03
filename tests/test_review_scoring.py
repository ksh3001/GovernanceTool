import pytest

from core.findings import Finding, FindingsFile
from core.review import ReviewFile, current_decisions, final_status, record_decision, stale_count
from core.scoring import compliance_score, summarise
from core.store import Store


def finding(cid, status, **kw):
    return Finding(control_id=cid, article=f"Art {cid}", title=f"Title {cid}", status=status, **kw)


def run_file(statuses, finished="2026-01-01T00:00:00+00:00"):
    return FindingsFile(app_id="a", framework="eu_ai_act", finished_at=finished,
                        findings=[finding(f"c{i}", s) for i, s in enumerate(statuses)])


# ---------- score ----------

def test_score_formula_matches_the_plan():
    # (met + 0.5 x partial) / applicable; not applicable is left out; not met and insufficient count as 0
    assert compliance_score(["met", "partial", "not_met", "insufficient_evidence", "not_applicable"]) == pytest.approx(1.5 / 4)
    assert compliance_score(["met", "met", "not_applicable"]) == 1.0
    assert compliance_score(["not_met"]) == 0.0


def test_score_is_none_when_nothing_applies():
    assert compliance_score([]) is None and compliance_score(["not_applicable"] * 3) is None


# ---------- decisions ----------

def test_confirm_keeps_status_and_note_is_optional():
    r, f = ReviewFile(app_id="a", framework="x"), finding("c1", "partial")
    d = record_decision(r, f, decision="confirmed", final_status=None, note="", reviewer="Asha", run="r1")
    assert (d.final_status, d.tool_status, d.decision) == ("partial", "partial", "confirmed")


def test_override_needs_a_different_status_and_a_note():
    r, f = ReviewFile(app_id="a", framework="x"), finding("c1", "met")
    with pytest.raises(ValueError, match="note is required"):
        record_decision(r, f, decision="overridden", final_status="not_met", note="  ", reviewer="Asha", run="r1")
    with pytest.raises(ValueError, match="same as the tool"):
        record_decision(r, f, decision="overridden", final_status="met", note="because", reviewer="Asha", run="r1")
    with pytest.raises(ValueError, match="Choose"):
        record_decision(r, f, decision="overridden", final_status=None, note="because", reviewer="Asha", run="r1")
    assert r.decisions == {} and r.history == []  # failed attempts leave no trace


def test_override_never_changes_the_tool_finding():
    r, f = ReviewFile(app_id="a", framework="x"), finding("c1", "met")
    record_decision(r, f, decision="overridden", final_status="partial", note="Logs lack retention.", reviewer="Asha", run="r1")
    assert f.status == "met" and r.decisions["c1"].final_status == "partial"


def test_history_keeps_every_decision_and_latest_wins():
    r, f = ReviewFile(app_id="a", framework="x"), finding("c1", "met")
    record_decision(r, f, decision="confirmed", final_status=None, note="", reviewer="Asha", run="r1")
    record_decision(r, f, decision="overridden", final_status="not_met", note="Changed my mind.", reviewer="Ravi", run="r1")
    assert len(r.history) == 2 and r.decisions["c1"].reviewer == "Ravi" and r.decisions["c1"].final_status == "not_met"


def test_reviewer_name_required():
    with pytest.raises(ValueError, match="reviewer"):
        record_decision(ReviewFile(app_id="a", framework="x"), finding("c1", "met"), decision="confirmed",
                        final_status=None, note="", reviewer=" ", run="r1")


# ---------- summary ----------

def test_dashboard_uses_reviewer_status_where_overridden():
    fs = run_file(["met", "partial", "not_met", "insufficient_evidence", "not_applicable"])
    review = ReviewFile(app_id="a", framework="eu_ai_act")
    record_decision(review, fs.findings[2], decision="overridden", final_status="partial", note="Policy exists.",
                    reviewer="Asha", run=fs.finished_at)
    record_decision(review, fs.findings[0], decision="confirmed", final_status=None, note="", reviewer="Asha", run=fs.finished_at)
    s = summarise(fs, review)
    assert s.counts == {"met": 1, "partial": 2, "not_met": 0, "insufficient_evidence": 1, "not_applicable": 1}
    assert s.score == pytest.approx(2 / 4) and s.tool_score == pytest.approx(1.5 / 4)
    assert (s.reviewed, s.overridden, s.applicable) == (2, 1, 4)


def test_gaps_list_not_met_first_then_insufficient_with_reviewer_note():
    fs = run_file(["insufficient_evidence", "not_met", "met"])
    review = ReviewFile(app_id="a", framework="eu_ai_act")
    record_decision(review, fs.findings[0], decision="overridden", final_status="not_met", note="No risk file exists.",
                    reviewer="Asha", run=fs.finished_at)
    gaps = summarise(fs, review).gaps
    assert [(g.control_id, g.status) for g in gaps] == [("c0", "not_met"), ("c1", "not_met")]
    assert gaps[0].rationale == "No risk file exists."


def test_summary_without_review():
    s = summarise(run_file(["met", "not_applicable"]), None)
    assert (s.reviewed, s.overridden, s.score, s.tool_score) == (0, 0, 1.0, 1.0)


def test_decisions_from_an_earlier_run_are_not_applied():
    old = run_file(["not_met"], finished="old")
    review = ReviewFile(app_id="a", framework="eu_ai_act")
    record_decision(review, old.findings[0], decision="overridden", final_status="met", note="Fine.", reviewer="Asha", run="old")
    new = run_file(["not_met"], finished="new")
    assert current_decisions(review, new) == {} and stale_count(review, new) == 1
    s = summarise(new, review)
    assert s.counts["not_met"] == 1 and s.stale_decisions == 1 and s.reviewed == 0
    assert final_status(new.findings[0], current_decisions(review, new)) == "not_met"


def test_review_roundtrip_in_store(tmp_path):
    store = Store(tmp_path)
    r = ReviewFile(app_id="a", framework="eu_ai_act")
    record_decision(r, finding("c1", "met"), decision="confirmed", final_status=None, note="ok", reviewer="Asha", run="r1")
    store.save("a", "review/eu_ai_act.json", r)
    assert store.load("a", "review/eu_ai_act.json", ReviewFile).decisions["c1"].note == "ok"
