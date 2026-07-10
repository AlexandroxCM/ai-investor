from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from ai_investor.core.models import Article
from ai_investor.plugins.news.composite import CompositeNews, dedup

NOW = datetime.now(timezone.utc)


def art(headline, tier=3, source="x", age_min=0):
    return Article(ticker="NVDA", headline=headline, body="b", tier=tier,
                   source=source, published=NOW - timedelta(minutes=age_min))


def test_dedup_kills_near_duplicates_keeps_higher_tier():
    articles = [
        art("NVIDIA announces record quarterly earnings results", tier=3, age_min=5),
        art("[8-K filing] NVIDIA record quarterly earnings announced", tier=1, age_min=60),
        art("Fed holds interest rates steady in July meeting", tier=3),
    ]
    kept = dedup(articles)
    assert len(kept) == 2
    survivors = {a.headline for a in kept}
    assert any("8-K" in h for h in survivors)          # filing beat the rehash
    assert any("Fed holds" in h for h in survivors)    # unrelated story kept


def test_dedup_keeps_distinct_stories():
    articles = [art("NVIDIA launches new Blackwell GPU line"),
                art("Apple faces antitrust probe in Europe")]
    assert len(dedup(articles)) == 2


def test_composite_survives_a_dead_provider():
    good = MagicMock()
    good.get_articles.return_value = [art("Working feed story")]
    dead = MagicMock()
    dead.get_articles.side_effect = RuntimeError("feed down")
    comp = CompositeNews([dead, good])
    out = comp.get_articles("NVDA")
    assert len(out) == 1
    assert out[0].headline == "Working feed story"


def test_composite_ranks_filings_first():
    p1 = MagicMock()
    p1.get_articles.return_value = [art("General market chatter", tier=3, age_min=1)]
    p2 = MagicMock()
    p2.get_articles.return_value = [art("[8-K filing] Material event", tier=1, age_min=120)]
    comp = CompositeNews([p1, p2])
    out = comp.get_articles("NVDA")
    assert out[0].tier == 1  # filing outranks fresher general news


def test_edgar_requires_contact_user_agent():
    from ai_investor.plugins.news.edgar import EdgarFilings
    with pytest.raises(RuntimeError, match="User-Agent"):
        EdgarFilings(user_agent="anonymous")


def test_edgar_parses_atom(monkeypatch):
    from ai_investor.plugins.news import edgar as edgar_mod
    atom = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>8-K - Current report</title>
        <summary>Item 2.02 Results of Operations</summary>
        <updated>2026-07-08T16:05:00-04:00</updated>
      </entry>
    </feed>"""
    fake_resp = MagicMock()
    fake_resp.content = atom
    fake_resp.raise_for_status = MagicMock()
    with patch.object(edgar_mod.requests, "get", return_value=fake_resp):
        e = edgar_mod.EdgarFilings("ai-investor test test@example.com")
        out = e.get_articles("NVDA", limit=5)
    assert len(out) == 1
    assert out[0].tier == 1
    assert "8-K" in out[0].headline
