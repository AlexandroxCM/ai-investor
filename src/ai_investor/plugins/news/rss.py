"""Free news via RSS. Default feed is Yahoo Finance per-ticker; add feeds
(PR Newswire, Reuters, sector blogs) in settings.yaml without code changes.
Feeds are fetched with an explicit timeout — a slow feed skips, never hangs."""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from ai_investor.core.interfaces.providers import NewsProvider
from ai_investor.core.models import Article

DEFAULT_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
]
TIMEOUT = 15


class RSSNews(NewsProvider):
    def __init__(self, feed_templates: list[str] | None = None):
        import feedparser
        self._fp = feedparser
        self.feeds = feed_templates or DEFAULT_FEEDS

    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]:
        articles: list[Article] = []
        for template in self.feeds:
            url = template.format(ticker=ticker)
            try:
                resp = requests.get(url, timeout=TIMEOUT,
                                    headers={"User-Agent": "ai-investor-rss"})
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[news:rss] feed timed out or failed, skipping: {e}")
                continue
            parsed = self._fp.parse(resp.content)
            for entry in parsed.entries[:limit]:
                published = datetime.now(timezone.utc)
                if getattr(entry, "published_parsed", None):
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                articles.append(Article(
                    ticker=ticker,
                    headline=entry.get("title", ""),
                    body=entry.get("summary", "")[:1000],
                    published=published))
        articles.sort(key=lambda a: a.published, reverse=True)
        return articles[:limit]
