"""FRED (St. Louis Fed) — free API key, covers the entire macro wishlist:
rates, CPI, GDP, employment, yield curve. https://fred.stlouisfed.org"""
from __future__ import annotations

import os

import requests

from ai_investor.core.interfaces.providers import MacroProvider

BASE = "https://api.stlouisfed.org/fred/series/observations"


class FredMacro(MacroProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing FRED_API_KEY — free key at fred.stlouisfed.org")

    def get_series(self, series_id: str, limit: int = 24) -> list[float]:
        resp = requests.get(BASE, params={
            "series_id": series_id, "api_key": self.api_key,
            "file_type": "json", "sort_order": "desc", "limit": limit}, timeout=20)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        values = [float(o["value"]) for o in reversed(obs) if o["value"] != "."]
        return values
