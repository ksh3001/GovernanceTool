import json

import pytest

from core.config import Settings
from core.llm import LLMClient, ReplayMiss


def settings(tmp_path, mode="fake"):
    return Settings(llm_mode=mode, demo_password="", azure_endpoint="", azure_api_key="",
                    azure_deployment="", azure_api_version="x", data_dir=tmp_path, packs_dir=tmp_path)


def test_fake_mode_uses_handler_and_logs(tmp_path):
    client = LLMClient(settings(tmp_path), fake_handler=lambda s, p: f"echo:{p}")
    result = client.complete("hello", purpose="test")
    assert result.text == "echo:hello" and result.mode == "fake"
    log = (tmp_path / "logs" / "llm_calls.jsonl").read_text().splitlines()
    assert json.loads(log[0])["purpose"] == "test"
    assert "hello" not in log[0]  # prompt text is not logged


def test_fake_default_is_safe_status(tmp_path):
    assert "insufficient_evidence" in LLMClient(settings(tmp_path)).complete("x").text


def test_replay_miss_raises(tmp_path):
    with pytest.raises(ReplayMiss):
        LLMClient(settings(tmp_path, "replay")).complete("never seen")


def test_replay_returns_recorded(tmp_path):
    live = LLMClient(settings(tmp_path, "live"))
    live._live = lambda system, prompt: "recorded"
    live.complete("q", system="s", purpose="p")
    replay = LLMClient(settings(tmp_path, "replay"))
    r = replay.complete("q", system="s", purpose="p")
    assert r.text == "recorded" and r.cached


def test_live_without_keys_fails_clearly(tmp_path):
    with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
        LLMClient(settings(tmp_path, "live")).complete("x")
