"""Combines news providers, deduplicates near-identical stories, and ranks
by signal tier. The design position: a curated handful of sources with
dedup beats 30 raw feeds — more duplicates just cost LLM calls."""
from __future__ import annotations

from ai_investor.core.interfaces.providers import NewsProvider
from ai_investor.core.models import Article

_STOP = {"the", "a", "an", "to", "of", "in", "on", "for", "and", "its", "is",
         "at", "as", "by", "with", "after", "amid", "says", "stock", "shares",
         "filing", "report", "current"}  # tier-prefix words, not story content


def _stem(word: str) -> str:
    """Crude suffix stripping so 'announces'/'announced'/'announcing' collide."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> set[str]:
    words = "".join(c.lower() if c.isalnum() else " " for c in text).split()
    return {_stem(w) for w in words if w not in _STOP and len(w) > 2}


def _similar(a: str, b: str, threshold: float = 0.55) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold


def dedup(articles: list[Article]) -> list[Article]:
    """Keep one article per story; on collision the higher-signal tier wins."""
    ranked = sorted(articles, key=lambda a: (a.tier, -a.published.timestamp()))
    kept: list[Article] = []
    for art in ranked:
        if not any(_similar(art.headline, k.headline) for k in kept):
            kept.append(art)
    return kept


class CompositeNews(NewsProvider):
    def __init__(self, providers: list[NewsProvider]):
        self.providers = providers

    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]:
        pooled: list[Article] = []
        for p in self.providers:
            try:
                pooled.extend(p.get_articles(ticker, limit))
            except Exception as e:  # one dead feed must not blind the agent
                print(f"[news:{type(p).__name__}] failed for {ticker}: {e}")
        unique = dedup(pooled)
        unique.sort(key=lambda a: (a.tier, -a.published.timestamp()))
        return unique[:limit]
