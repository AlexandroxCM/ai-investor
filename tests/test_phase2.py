import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ai_investor.audit.store import AuditStore
from ai_investor.core.enums import Signal
from ai_investor.core.models import AgentReport, RunRecord, TradeProposal
from ai_investor.orchestrator.registry import Registry
from pathlib import Path

ROOT = Path(__file__).parent.parent


def make_record(run_id="t-1", ticker="NVDA"):
    return RunRecord(
        run_id=run_id,
        reports=[AgentReport(agent="technical", ticker=ticker, score=0.5,
                             confidence=0.7, summary="s")],
        proposal=TradeProposal(ticker=ticker, signal=Signal.BUY, quantity=1,
                               confidence=0.8, thesis="t"))


def test_audit_store_roundtrip(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    store.save(make_record())
    hist = store.history()
    assert len(hist) == 1
    assert hist[0]["ticker"] == "NVDA"
    assert hist[0]["signal"] == "buy"
    full = json.loads(store.explain("t-1"))
    assert full["proposal"]["thesis"] == "t"


def test_audit_store_filters_by_ticker(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    store.save(make_record("a", "NVDA"))
    store.save(make_record("b", "AAPL"))
    assert len(store.history("NVDA")) == 1
    assert len(store.history()) == 2


def test_registry_rejects_unknown_plugin(tmp_path):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text("""
plugins: {llm: nope, market_data: fake, news: fake, broker: fake}
run: {starting_cash: 1000.0, audit_dir: runs}
""")
    try:
        Registry(cfg)
        assert False, "should have raised"
    except ValueError as e:
        assert "unknown llm" in str(e)


def test_openai_compat_llm_parses_response(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from ai_investor.plugins.llm.providers import OpenAICompatLLM
    llm = OpenAICompatLLM(preset="groq")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "hello"}}]}
    fake_resp.raise_for_status = MagicMock()
    with patch("ai_investor.plugins.llm.providers.requests.post",
               return_value=fake_resp) as post:
        out = llm.complete("hi", system="sys")
    assert out == "hello"
    sent = post.call_args.kwargs["json"]
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert sent["temperature"] == 0.0


def test_yfinance_plugin_maps_history_to_bars():
    import pandas as pd
    from ai_investor.plugins.market_data.yfinance_ import YFinanceData

    data = YFinanceData()
    idx = pd.to_datetime(["2026-07-01", "2026-07-02"], utc=True)
    df = pd.DataFrame({"Open": [100.0, 101.0], "High": [102.0, 103.0],
                       "Low": [99.0, 100.0], "Close": [101.0, 102.5],
                       "Volume": [1_000_000, 2_000_000]}, index=idx)
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = df
    data._cache["NVDA"] = fake_ticker

    bars = data.get_bars("NVDA", 30)
    assert len(bars) == 2
    assert bars[-1].close == 102.5
    assert data.last_price("NVDA") == 102.5
