from pathlib import Path

from ai_investor.agents.risk_manager import RiskManager
from ai_investor.core.benchmark import ShadowBenchmark
from ai_investor.core.enums import OrderStatus, RiskAction, Signal
from ai_investor.core.models import Order, PortfolioState, TradeProposal
from ai_investor.plugins.fakes import FakeBroker, FakeMarketData

RULES = Path(__file__).parent.parent / "config" / "risk_rules.yaml"


def test_benchmark_tracks_deposits():
    data = FakeMarketData()
    b = ShadowBenchmark(data, "VOO")
    b.deposit(1000)
    assert b.deposited == 1000
    assert abs(b.value() - 1000) < 0.01  # flat price => value == deposit


def test_benchmark_dividends_reinvest():
    data = FakeMarketData()
    b = ShadowBenchmark(data, "VOO")
    b.deposit(1000)
    paid = b.apply_dividends(365)
    assert 12 < paid < 14            # ~1.3% yield on $1000
    assert b.value() > 1000


def test_slippage_fills_against_you():
    data = FakeMarketData()
    broker = FakeBroker(data, starting_cash=10_000, slippage_bps=50)
    mid = data.last_price("NVDA")
    o = broker.submit(Order(ticker="NVDA", signal=Signal.BUY, quantity=1))
    assert o.status == OrderStatus.FILLED
    assert o.fill_price > mid        # buys fill higher than mid


def test_broker_pays_dividends_on_holdings():
    data = FakeMarketData()
    broker = FakeBroker(data, starting_cash=10_000, slippage_bps=0)
    broker.submit(Order(ticker="VOO", signal=Signal.BUY, quantity=10))
    cash_before = broker.cash
    paid = broker.apply_dividends(365)
    assert paid > 0
    assert broker.cash == cash_before + paid


def test_kill_switch_halts_and_stays_halted(tmp_path):
    state = tmp_path / "risk_state.json"
    rm = RiskManager(RULES, state_path=state)
    prop = TradeProposal(ticker="TEST", signal=Signal.BUY, quantity=1,
                         confidence=0.9, thesis="t")

    # establish high-water mark at 1000
    rm.evaluate(prop, PortfolioState(cash=1000, equity=1000), last_price=10)
    # 25% drawdown (limit is 20%) => halt
    v = rm.evaluate(prop, PortfolioState(cash=750, equity=750), last_price=10)
    assert v.action == RiskAction.REJECT
    assert "kill_switch" in v.rules_triggered

    # equity recovers, but halt persists until manual reset
    rm2 = RiskManager(RULES, state_path=state)  # fresh instance, same state file
    v2 = rm2.evaluate(prop, PortfolioState(cash=1000, equity=1000), last_price=10)
    assert "kill_switch" in v2.rules_triggered
