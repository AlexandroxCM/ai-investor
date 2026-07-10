"""Free news via RSS. Default feed is Yahoo Finance per-ticker; add feeds
(PR Newswire, Reuters, sector blogs) in settings.yaml without code changes."""
from __future__ import annotations

from datetime import datetime, timezone

from ai_investor.core.interfaces.providers import NewsProvider
from ai_investor.core.models import Article

DEFAULT_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
]


class RSSNews(NewsProvider):
    def __init__(self, feed_templates: list[str] | None = None):
        import feedparser
        self._fp = feedparser
        self.feeds = feed_templates or DEFAULT_FEEDS

    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]:
        articles: list[Article] = []
        for template in self.feeds:
            parsed = self._fp.parse(template.format(ticker=ticker))
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
