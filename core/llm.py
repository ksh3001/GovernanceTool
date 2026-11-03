"""The only place that talks to a model.

Modes: fake (deterministic, no network), live (Azure OpenAI, results cached for
replay), replay (answers only from the cache, never calls the network).
Every call is appended to <data_dir>/logs/llm_calls.jsonl. Keys and prompt text
are never logged.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Callable

from .config import Settings

FakeHandler = Callable[[str, str], str]


class ReplayMiss(RuntimeError):
    """Replay mode was asked for a call that was never recorded."""


@dataclass
class LLMResult:
    text: str
    mode: str
    cached: bool = False


def _key(system: str, prompt: str) -> str:
    """Cache key from the exact text sent. The purpose (which carries the app id) is left out on purpose,
    so re-onboarding the same app still finds its recorded answers."""
    return hashlib.sha256(json.dumps([system, prompt]).encode()).hexdigest()


class LLMClient:
    def __init__(self, settings: Settings, fake_handler: FakeHandler | None = None):
        self.settings = settings
        self.mode = settings.llm_mode
        self.fake_handler = fake_handler or (lambda system, prompt: '{"status": "insufficient_evidence"}')
        self.log_path = settings.data_dir / "logs" / "llm_calls.jsonl"
        self.cache_path = settings.data_dir / "replay" / "cache.jsonl"
        self._client = None

    def complete(self, prompt: str, system: str = "", purpose: str = "general") -> LLMResult:
        started = time.time()
        key = _key(system, prompt)
        cached = False
        if self.mode == "fake":
            text = self.fake_handler(system, prompt)
        elif self.mode == "replay":
            text = self._cache_get(key, purpose)
            cached = True
        else:
            text = self._live(system, prompt)
            self._cache_put(key, text)
        self._log({"purpose": purpose, "mode": self.mode, "key": key, "cached": cached,
                   "prompt_chars": len(prompt), "response_chars": len(text),
                   "seconds": round(time.time() - started, 3)})
        return LLMResult(text=text, mode=self.mode, cached=cached)

    def _live(self, system: str, prompt: str) -> str:
        s = self.settings
        if not (s.azure_endpoint and s.azure_api_key and s.azure_deployment):
            raise RuntimeError(
                "Live mode needs AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT")
        if self._client is None:
            from openai import AzureOpenAI
            self._client = AzureOpenAI(azure_endpoint=s.azure_endpoint, api_key=s.azure_api_key,
                                       api_version=s.azure_api_version)
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        resp = self._client.chat.completions.create(model=s.azure_deployment, messages=messages, temperature=0)
        return resp.choices[0].message.content or ""

    def _cache_get(self, key: str, purpose: str = "") -> str:
        paths = [p for p in (self.settings.replay_cache, self.cache_path) if p]
        for path in paths:
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip() and json.loads(line)["key"] == key:
                        return json.loads(line)["text"]
        raise ReplayMiss(f"No recorded response for this call ({purpose or 'unknown'}). The saved demo run does not "
                         "cover this application as it is now; record it once in live mode.")

    def _cache_put(self, key: str, text: str) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "text": text}) + "\n")

    def _log(self, entry: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
