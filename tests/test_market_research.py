from pathlib import Path
from unittest.mock import MagicMock

from ai_investor.agents.market_research import MarketResearchAgent
from ai_investor.plugins.fakes import FakeLLM, FakeMarketData


def make_agent():
    return MarketResearchAgent(FakeMarketData(), FakeLLM(),
                               ["NVDA", "AAPL", "MSFT", "KO", "PEP"],
                               index_ticker="VOO")


def test_metrics_are_sane():
    m = make_agent().compute_metrics()
    assert 0.0 <= m["breadth"] <= 1.0
    assert m["regime"] in ("risk-on", "neutral", "risk-off")
    assert m["universe_size"] == 5


def test_briefing_roundtrip_and_report(tmp_path):
    agent = make_agent()
    b = agent.briefing(macro_summary="Fed on hold")
    MarketResearchAgent.save(b, tmp_path)
    import json
    from datetime import datetime, timezone
    # loader keys off today's date, which save used
    loaded = MarketResearchAgent.load_today(tmp_path)
    assert loaded is not None
    rep = MarketResearchAgent.as_report(loaded, "NVDA")
    assert rep.agent == "regime"
    assert rep.ticker == "NVDA"
    assert -1 <= rep.score <= 1


def test_dead_llm_still_produces_briefing():
    llm = MagicMock()
    llm.complete.side_effect = RuntimeError("quota")
    agent = MarketResearchAgent(FakeMarketData(), llm, ["NVDA"], "VOO")
    b = agent.briefing()
    assert "unavailable" in b["briefing"]
    assert b["metrics"]["regime"] in ("risk-on", "neutral", "risk-off")


def test_no_briefing_file_means_none(tmp_path):
    assert MarketResearchAgent.load_today(tmp_path) is None
