from pathlib import Path

import yaml

from ai_investor.core.enums import Signal
from ai_investor.core.models import Order
from ai_investor.core.benchmark import PersistentBenchmark
from ai_investor.persistence.state import StateStore
from ai_investor.plugins.broker.paper import PaperBroker
from ai_investor.plugins.fakes import FakeMarketData
from ai_investor.orchestrator.registry import Registry


def test_paper_broker_state_survives_restart(tmp_path):
    data = FakeMarketData()
    store = StateStore(tmp_path / "state.db")

    b1 = PaperBroker(data, store, slippage_bps=0)
    b1.deposit(1000)
    b1.submit(Order(ticker="NVDA", signal=Signal.BUY, quantity=1))
    cash_after, pos_after = b1.cash, dict(b1.positions)

    b2 = PaperBroker(data, StateStore(tmp_path / "state.db"), slippage_bps=0)
    assert abs(b2.cash - cash_after) < 1e-6
    assert "NVDA" in b2.positions
    assert abs(b2.positions["NVDA"].quantity - pos_after["NVDA"].quantity) < 1e-9


def test_benchmark_state_survives_restart(tmp_path):
    data = FakeMarketData()
    store = StateStore(tmp_path / "state.db")
    bm1 = PersistentBenchmark(data, store)
    bm1.deposit(500)

    bm2 = PersistentBenchmark(data, StateStore(tmp_path / "state.db"))
    assert bm2.deposited == 500
    assert abs(bm2.value() - bm1.value()) < 0.01


def make_settings(tmp_path):
    cfg = {
        "plugins": {"llm": "fake", "market_data": "fake", "news": "fake",
                    "broker": "paper", "notifier": "console", "macro": "fake"},
        "universe": {"watchlist": ["NVDA"]},
        "run": {"starting_cash": 1000.0, "audit_dir": str(tmp_path / "runs"),
                "slippage_bps": 0},
        "benchmark": {"ticker": "VOO"},
    }
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


def test_registry_seeds_paper_broker_exactly_once(tmp_path):
    cfg = make_settings(tmp_path)

    r1 = Registry(cfg)
    assert r1.broker.portfolio().cash == 1000.0
    r1.broker.submit(Order(ticker="NVDA", signal=Signal.BUY, quantity=1))
    cash_after_buy = r1.broker.portfolio().cash

    r2 = Registry(cfg)  # restart: no re-seed, state carried over
    assert abs(r2.broker.portfolio().cash - cash_after_buy) < 1e-6
    assert "NVDA" in {pos.ticker for pos in r2.broker.portfolio().positions}
    assert r2.benchmark.deposited == 1000.0  # not 2000


def test_deposit_funds_both_sides(tmp_path):
    cfg = make_settings(tmp_path)
    reg = Registry(cfg)
    reg.broker.deposit(100)
    reg.benchmark.deposit(100)
    assert reg.broker.portfolio().cash == 1100.0
    assert reg.benchmark.deposited == 1100.0
