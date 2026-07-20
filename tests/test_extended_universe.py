import json
import time
from unittest.mock import patch

from ai_investor.screener import universe as U


def test_yahoo_screen_is_primary(tmp_path):
    fake = [f"T{i}" for i in range(400)]
    with patch.object(U, "_yahoo_market_screen", return_value=fake):
        out = U.load_extended_universe(tmp_path)
    assert "T0" in out
    assert set(U.TOP_ETFS) <= set(out)
    data = json.loads((tmp_path / "universe_cache.json").read_text())
    assert data["source"] == "yahoo market screen"


def test_wikipedia_is_fallback(tmp_path):
    with patch.object(U, "_yahoo_market_screen", side_effect=RuntimeError("down")):
        with patch.object(U, "_wikipedia_index_lists",
                          return_value=["AAA", "BRK-B"]):
            out = U.load_extended_universe(tmp_path)
    assert "AAA" in out and "BRK-B" in out


def test_core_is_final_floor(tmp_path):
    with patch.object(U, "_yahoo_market_screen", side_effect=RuntimeError("down")):
        with patch.object(U, "_wikipedia_index_lists",
                          side_effect=RuntimeError("also down")):
            out = U.load_extended_universe(tmp_path)
    assert out == U.DEFAULT_UNIVERSE


def test_cache_respected_and_expires(tmp_path):
    cache = tmp_path / "universe_cache.json"
    cache.write_text(json.dumps({"fetched_at": time.time(),
                                 "tickers": ["CACHED"]}))
    assert U.load_extended_universe(tmp_path) == ["CACHED"]
    cache.write_text(json.dumps({"fetched_at": time.time() - 40 * 86400,
                                 "tickers": ["STALE"]}))
    with patch.object(U, "_yahoo_market_screen", return_value=["FRESH"] * 400):
        out = U.load_extended_universe(tmp_path)
    assert "STALE" not in out


def test_tiny_screen_result_rejected():
    import pytest
    with patch("yfinance.screen", return_value={"quotes": [{"symbol": "ONLY1"}]}):
        with pytest.raises(RuntimeError, match="only"):
            U._yahoo_market_screen()
