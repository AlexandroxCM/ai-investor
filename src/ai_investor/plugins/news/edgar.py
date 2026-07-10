"""SEC EDGAR filing feed. 8-Ks are companies legally disclosing material
events — the highest-signal 'news' available, free. SEC requires a
User-Agent identifying you (name + contact) or requests get blocked."""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from ai_investor.core.interfaces.providers import NewsProvider
from ai_investor.core.models import Article

ATOM_URL = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            "&CIK={ticker}&type={ftype}&dateb=&owner=include&count={limit}&output=atom")


class EdgarFilings(NewsProvider):
    def __init__(self, user_agent: str, filing_types: tuple[str, ...] = ("8-K",)):
        import feedparser
        self._fp = feedparser
        if not user_agent or "@" not in user_agent:
            raise RuntimeError(
                "EDGAR requires a User-Agent with contact info, e.g. "
                "'ai-investor personal-project you@example.com' — set it in settings.yaml")
        self.user_agent = user_agent
        self.filing_types = filing_types

    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]:
        articles: list[Article] = []
        for ftype in self.filing_types:
            url = ATOM_URL.format(ticker=ticker, ftype=ftype, limit=limit)
            resp = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=20)
            resp.raise_for_status()
            parsed = self._fp.parse(resp.content)
            for entry in parsed.entries[:limit]:
                published = datetime.now(timezone.utc)
                if getattr(entry, "updated_parsed", None):
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                articles.append(Article(
                    ticker=ticker,
                    headline=f"[{ftype} filing] {entry.get('title', '')}",
                    body=entry.get("summary", "")[:1000],
                    published=published,
                    source="sec-edgar",
                    tier=1))
        return articles[:limit]
