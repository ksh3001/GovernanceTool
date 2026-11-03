import pytest

from core.config import ROOT, Settings
from core.demo import assess_sample, describe, run_samples, sample_folders
from core.llm import LLMClient, ReplayMiss
from tests.test_assess import A_REPLIES, Scripted

SAMPLES = ROOT / "samples"
HR = SAMPLES / "hr_cv_screener"


def settings(data_dir, mode="live", cache=None):
    return Settings(llm_mode=mode, demo_password="", azure_endpoint="", azure_api_key="", azure_deployment="",
                    azure_api_version="x", data_dir=data_dir, packs_dir=ROOT / "control_packs", replay_cache=cache)


def recording_client(data_dir, handler):
    client = LLMClient(settings(data_dir, "live"))
    client._live = handler  # stands in for the Azure call
    return client


def test_replay_reproduces_a_recorded_run_from_another_folder_and_app_id(tmp_path):
    handler = Scripted(A_REPLIES, default=None)
    live = assess_sample(HR, recording_client(tmp_path / "rec", lambda system, prompt: handler(system, prompt)))
    cache = tmp_path / "rec" / "replay" / "cache.jsonl"
    assert cache.is_file()

    # A fresh data folder, the saved file given explicitly, and a different app id: the cache must still hit.
    replay_llm = LLMClient(settings(tmp_path / "other", "replay", cache))
    replayed = assess_sample(HR, replay_llm)
    assert replayed.findings.llm_mode == "replay"
    assert [(f.control_id, f.status, [c.excerpt_sha256 for c in f.citations]) for f in replayed.findings.findings] == \
           [(f.control_id, f.status, [c.excerpt_sha256 for c in f.citations]) for f in live.findings.findings]
    assert replayed.agreement.agreed == live.agreement.agreed


def test_cache_key_ignores_the_purpose_label(tmp_path):
    live = LLMClient(settings(tmp_path, "live"))
    live._live = lambda system, prompt: "recorded"
    live.complete("same prompt", system="s", purpose="assess:app-1:eu-art-12")
    replay = LLMClient(settings(tmp_path, "replay"))
    assert replay.complete("same prompt", system="s", purpose="assess:app-2:eu-art-12").text == "recorded"


def test_missing_recording_is_reported_with_the_control_not_crashing(tmp_path):
    report = run_samples(LLMClient(settings(tmp_path, "replay", tmp_path / "empty.jsonl")), [HR])
    assert not report.ok and report.runs == []
    assert "hr_cv_screener" in report.problems[0] and "No recorded response" in report.problems[0]
    assert any(line.startswith("\nPROBLEM") for line in describe(report))


def test_changed_prompt_no_longer_matches_the_recording(tmp_path):
    client = recording_client(tmp_path, lambda s, p: "recorded")
    client.complete("original prompt", system="s")
    cache = tmp_path / "replay" / "cache.jsonl"
    replay = LLMClient(settings(tmp_path / "x", "replay", cache))
    assert replay.complete("original prompt", system="s").text == "recorded"  # the recording itself is readable
    with pytest.raises(ReplayMiss):
        replay.complete("edited prompt", system="s")


def test_describe_lists_every_control_and_the_agreement(tmp_path):
    handler = Scripted(A_REPLIES, default=None)
    report = run_samples(recording_client(tmp_path, lambda s, p: handler(s, p)), [HR])
    text = "\n".join(describe(report))
    assert "Article 12" in text and "Agreement with the key" in text and "DRAFT KEY" in text
    assert "Trap case" in text


def test_sample_folders_found():
    assert {p.name for p in sample_folders()} == {"hr_cv_screener", "support_chatbot"}


def test_default_settings_point_at_the_demo_cache(monkeypatch):
    from core.config import load_settings
    monkeypatch.delenv("PROVENIX_REPLAY_CACHE", raising=False)
    assert load_settings().replay_cache == ROOT / "demo" / "replay_cache.jsonl"
