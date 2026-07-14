from datetime import date
from unittest.mock import MagicMock, patch

from ai_investor.screener.earnings import EarningsRadar

IDX = """Form Type   Company Name    CIK   Date Filed  File Name
--------------------------------------------------------------
10-Q        SOMECO INC      111   20260713    edgar/data/111/x.txt
8-K         NVIDIA CORP     1045810   20260713    edgar/data/1045810/y.txt
8-K         UNRELATED LLC   999999999 20260713    edgar/data/9/z.txt
"""

TICKER_JSON = {"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
               "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}


def radar():
    return EarningsRadar("ai-investor test test@example.com")


def test_finds_universe_reporters():
    r = radar()

    def fake_get(url, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        if "company_tickers" in url:
            resp.json.return_value = TICKER_JSON
        else:
            resp.text = IDX
        return resp

    from ai_investor.screener import earnings as mod
    with patch.object(mod.requests, "get", side_effect=fake_get):
        out = r.todays_reporters(["NVDA", "AAPL", "MSFT"], day=date(2026, 7, 13))
    assert out == ["NVDA"]  # filed today, in universe; AAPL didn't file


def test_weekend_returns_empty():
    r = radar()
    resp = MagicMock()
    resp.status_code = 404
    from ai_investor.screener import earnings as mod
    with patch.object(mod.requests, "get", return_value=resp):
        assert r.todays_reporters(["NVDA"], day=date(2026, 7, 12)) == []


def test_radar_failure_never_blocks():
    r = radar()
    from ai_investor.screener import earnings as mod
    with patch.object(mod.requests, "get", side_effect=RuntimeError("sec down")):
        assert r.todays_reporters(["NVDA"]) == []
