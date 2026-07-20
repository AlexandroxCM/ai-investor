"""LLM providers. One OpenAI-compatible client covers Groq, Gemini, and
OpenRouter free tiers — they all speak the same API shape. Ollama for local."""
from __future__ import annotations

import os
import time

import requests

from ai_investor.core.interfaces.providers import LLMProvider

PRESETS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        # 2.5-flash-lite has the healthiest free quota after Google's Dec 2025 cuts
        "model": "gemini-2.5-flash-lite",
        "key_env": "GEMINI_API_KEY",
    },
}


class OpenAICompatLLM(LLMProvider):
    def __init__(self, preset: str = "groq", model: str | None = None,
                 base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.0, min_interval: float = 2.0,
                 max_retries: int = 5):
        cfg = PRESETS.get(preset, {})
        self.base_url = base_url or cfg.get("base_url", "")
        self.model = model or cfg.get("model", "")
        self.api_key = api_key or os.environ.get(cfg.get("key_env", ""), "")
        self.temperature = temperature
        self.min_interval = min_interval   # pace calls under free-tier RPM limits
        self.max_retries = max_retries
        self._last_call = 0.0
        if not self.api_key:
            raise RuntimeError(
                f"Missing API key — set {cfg.get('key_env', 'the provider key')} in .env")

    def complete(self, prompt: str, system: str = "") -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages,
                   "temperature": self.temperature}
        for attempt in range(self.max_retries):
            gap = self.min_interval - (time.monotonic() - self._last_call)
            if gap > 0:
                time.sleep(gap)
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload, timeout=60)
            except requests.exceptions.RequestException as e:
                # mid-cycle network drop: wait for the connection to come back
                wait = 2 ** attempt * 10
                print(f"[llm] connection failed ({type(e).__name__}), waiting "
                      f"{wait}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait)
                continue
            self._last_call = time.monotonic()
            if resp.status_code == 429:
                wait = float(resp.headers.get("retry-after", 2 ** attempt * 3))
                print(f"[llm] rate limited, waiting {wait:.0f}s "
                      f"(attempt {attempt + 1}/{self.max_retries})")
                if attempt == 0:  # show the quota detail once — 'limit: 0' means wrong model/tier
                    print(f"[llm] detail: {resp.text[:200]}")
                time.sleep(wait + 0.5)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        raise RuntimeError("LLM rate-limit retries exhausted — try again later "
                           "or lower screener top_n")


class OllamaLLM(LLMProvider):
    def __init__(self, model: str = "qwen2.5:14b",
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def complete(self, prompt: str, system: str = "") -> str:
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "system": system,
                  "stream": False, "options": {"temperature": 0}},
            timeout=300)
        resp.raise_for_status()
        return resp.json()["response"]
