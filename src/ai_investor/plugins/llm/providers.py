"""LLM providers. One OpenAI-compatible client covers Groq, Gemini, and
OpenRouter free tiers — they all speak the same API shape. Ollama for local."""
from __future__ import annotations

import os

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
        "model": "gemini-2.0-flash",
        "key_env": "GEMINI_API_KEY",
    },
}


class OpenAICompatLLM(LLMProvider):
    def __init__(self, preset: str = "groq", model: str | None = None,
                 base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.0):
        cfg = PRESETS.get(preset, {})
        self.base_url = base_url or cfg.get("base_url", "")
        self.model = model or cfg.get("model", "")
        self.api_key = api_key or os.environ.get(cfg.get("key_env", ""), "")
        self.temperature = temperature
        if not self.api_key:
            raise RuntimeError(
                f"Missing API key — set {cfg.get('key_env', 'the provider key')} in .env")

    def complete(self, prompt: str, system: str = "") -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages,
                  "temperature": self.temperature},
            timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


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
