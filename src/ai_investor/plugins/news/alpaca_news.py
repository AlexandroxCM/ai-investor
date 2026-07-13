"""Alpaca's News API — professional newswire content, free with any Alpaca
account (same keys as the broker). Higher signal than generic RSS, so it
enters the composite at earnings tier (2)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from ai_investor.core.interfaces.providers import NewsProvider
from ai_investor.core.models import Article

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"


class AlpacaNews(NewsProvider):
    def __init__(self, api_key: str | None = None, secret: str | None = None):
        key = api_key or os.environ.get("ALPACA_API_KEY", "")
        sec = secret or os.environ.get("ALPACA_SECRET_KEY", "")
        if not key or not sec:
            raise RuntimeError("AlpacaNews needs ALPACA_API_KEY / ALPACA_SECRET_KEY")
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}

    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]:
        resp = requests.get(NEWS_URL, headers=self.headers,
                            params={"symbols": ticker, "limit": limit}, timeout=15)
        resp.raise_for_status()
        articles = []
        for item in resp.json().get("news", []):
            published = datetime.now(timezone.utc)
            if item.get("created_at"):
                published = datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00"))
            articles.append(Article(
                ticker=ticker,
                headline=item.get("headline", ""),
                body=(item.get("summary") or item.get("headline", ""))[:1000],
                published=published,
                source=f"alpaca:{item.get('source', 'newswire')}",
                tier=2))
        return articles
