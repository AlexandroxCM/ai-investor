from pathlib import Path

import yaml

from ai_investor.orchestrator.pipeline import Pipeline
from ai_investor.orchestrator.registry import Registry


def make_settings(tmp_path):
    cfg = {"plugins": {"llm": "fake", "market_data": "fake", "news": "fake",
                       "broker": "fake", "notifier": "console", "macro": "fake"},
           "universe": {"watchlist": ["NVDA"]},
           "run": {"starting_cash": 1000.0, "audit_dir": str(tmp_path / "runs"),
                   "slippage_bps": 0},
           "benchmark": {"ticker": "VOO"}}
    p = tmp_path / "settings.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def make_rules(tmp_path):
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.90,
             "min_confidence": 0.60}
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(rules))
    return p


def test_full_cycle_on_fakes(tmp_path):
    reg = Registry(make_settings(tmp_path))
    pipe = Pipeline(reg, make_rules(tmp_path))
    rec = pipe.run_cycle("NVDA", budget=200)
    assert {r.agent for r in rec.reports} >= {"technical", "fundamental",
                                              "news", "macro"}
    assert rec.proposal is not None
    assert rec.verdict is not None
    assert (tmp_path / "runs" / f"{rec.run_id}.json").exists()


def test_deterministic_market_data(tmp_path):
    reg = Registry(make_settings(tmp_path))
    a = reg.market_data.get_bars("AAPL", 30)
    b = reg.market_data.get_bars("AAPL", 30)
    assert [x.close for x in a] == [x.close for x in b]
