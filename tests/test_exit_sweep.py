from pathlib import Path

import yaml

from ai_investor.core.models import Position
from ai_investor.orchestrator.pipeline import Pipeline
from ai_investor.orchestrator.registry import Registry


def make_registry(tmp_path):
    cfg = {"plugins": {"llm": "fake", "market_data": "fake", "news": "fake",
                       "broker": "fake", "notifier": "console", "macro": "fake"},
           "universe": {"watchlist": ["NVDA"]},
           "run": {"starting_cash": 10_000.0, "audit_dir": str(tmp_path / "runs"),
                   "slippage_bps": 0},
           "benchmark": {"ticker": "VOO"}}
    p = tmp_path / "settings.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return Registry(p)


def make_rules(tmp_path, stop=0.15, take=0.50):
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.90,
             "min_confidence": 0.60, "stop_loss_pct": stop,
             "take_profit_pct": take}
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(rules))
    return p


def test_stop_loss_fires_and_sells(tmp_path):
    reg = make_registry(tmp_path)
    price = reg.market_data.last_price("NVDA")
    # bought at double today's price => -50% loss, way past the 15% stop
    reg.broker.positions["NVDA"] = Position(ticker="NVDA", quantity=2,
                                            avg_cost=price * 2)
    pipe = Pipeline(reg, make_rules(tmp_path))
    records = pipe.exit_sweep()
    assert len(records) == 1
    assert records[0].strategy == "risk_exit"
    assert "stop_loss" in records[0].verdict.note
    assert records[0].order.status.value == "filled"
    assert "NVDA" not in reg.broker.positions  # fully exited


def test_take_profit_fires(tmp_path):
    reg = make_registry(tmp_path)
    price = reg.market_data.last_price("NVDA")
    reg.broker.positions["NVDA"] = Position(ticker="NVDA", quantity=1,
                                            avg_cost=price / 2)  # +100% gain
    pipe = Pipeline(reg, make_rules(tmp_path))
    records = pipe.exit_sweep()
    assert len(records) == 1
    assert "take_profit" in records[0].verdict.note


def test_healthy_positions_untouched(tmp_path):
    reg = make_registry(tmp_path)
    price = reg.market_data.last_price("NVDA")
    reg.broker.positions["NVDA"] = Position(ticker="NVDA", quantity=1,
                                            avg_cost=price)  # flat
    pipe = Pipeline(reg, make_rules(tmp_path))
    assert pipe.exit_sweep() == []
