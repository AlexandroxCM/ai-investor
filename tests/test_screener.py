from ai_investor.plugins.fakes import FakeMarketData
from ai_investor.screener.screener import Screener
from ai_investor.screener.universe import DEFAULT_UNIVERSE, SP100, TOP_ETFS


def test_universe_is_sane():
    assert len(SP100) >= 90
    assert "NVDA" in SP100 and "VOO" in TOP_ETFS
    assert len(DEFAULT_UNIVERSE) == len(SP100) + len(TOP_ETFS)


def test_screener_ranks_and_limits():
    data = FakeMarketData()
    sc = Screener(data, ["NVDA", "AAPL", "MSFT", "VOO", "QQQ", "KO", "PEP"],
                  top_n=3, min_dollar_volume=0)
    picks = sc.top_candidates()
    assert len(picks) == 3
    # deterministic fake data => deterministic ranking
    assert picks == sc.top_candidates()


def test_holdings_always_included():
    data = FakeMarketData()
    sc = Screener(data, ["NVDA", "AAPL", "MSFT"], top_n=2, min_dollar_volume=0)
    picks = sc.top_candidates(always_include=["ZZZHELD"])
    assert "ZZZHELD" in picks


def test_filters_apply():
    data = FakeMarketData()
    sc = Screener(data, ["NVDA"], top_n=5, min_price=10_000)  # impossible floor
    assert sc.top_candidates() == []
