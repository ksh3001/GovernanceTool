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


def _key(system: str, prompt: str, purpose: str) -> str:
    return hashlib.sha256(json.dumps([purpose, system, prompt]).encode()).hexdigest()


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
        key = _key(system, prompt, purpose)
        cached = False
        if self.mode == "fake":
            text = self.fake_handler(system, prompt)
        elif self.mode == "replay":
            text = self._cache_get(key)
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

    def _cache_get(self, key: str) -> str:
        if self.cache_path.is_file():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                if entry["key"] == key:
                    return entry["text"]
        raise ReplayMiss("No recorded response for this call; run once in live mode first.")

    def _cache_put(self, key: str, text: str) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "text": text}) + "\n")

    def _log(self, entry: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
