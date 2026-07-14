from pathlib import Path

import yaml

from ai_investor.agents.risk_manager import RiskManager
from ai_investor.core.enums import RiskAction, Signal
from ai_investor.core.models import PortfolioState, TradeProposal

SECTORS = {"SCHW": "Financials", "COF": "Financials", "V": "Financials",
           "TMO": "Health Care"}
PRICES = {"SCHW": 100.0, "COF": 100.0, "V": 100.0, "TMO": 100.0}


def make_rm(tmp_path):
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.20,
             "min_confidence": 0.60, "max_sector_pct": 0.40}
    rp = tmp_path / "rules.yaml"
    rp.write_text(yaml.safe_dump(rules))
    return RiskManager(rp, state_path=tmp_path / "s.json",
                       sector_of=SECTORS.get, price_of=PRICES.get)


def prop(ticker, qty):
    return TradeProposal(ticker=ticker, signal=Signal.BUY, quantity=qty,
                         confidence=0.9, thesis="t")


def test_pending_sector_exposure_blocks_pileup(tmp_path):
    rm = make_rm(tmp_path)
    pf = PortfolioState(cash=1000.0, equity=1000.0, positions=[])  # nothing filled yet
    pending = {"cash": 350.0, "sectors": {"Financials": 350.0}}    # queued this cycle
    # wants $200 more financials; only $50 sector headroom (40% of 1000 - 350)
    v = rm.evaluate(prop("COF", 2.0), pf, last_price=100, pending=pending)
    assert v.action == RiskAction.RESIZE
    assert v.rules_triggered == ["max_sector_pct"]
    assert v.approved_quantity * 100 <= 50 + 1e-6


def test_pending_cash_respected(tmp_path):
    rm = make_rm(tmp_path)
    pf = PortfolioState(cash=1000.0, equity=1000.0, positions=[])
    pending = {"cash": 880.0, "sectors": {"Financials": 880.0}}  # nearly all committed
    v = rm.evaluate(prop("TMO", 2.0), pf, last_price=100, pending=pending)
    # only $20 above the 10% cash floor remains -> reject or tiny resize
    assert v.action in (RiskAction.REJECT, RiskAction.RESIZE)
    if v.action == RiskAction.RESIZE:
        assert v.approved_quantity * 100 <= 20 + 1e-6


def test_no_pending_behaves_as_before(tmp_path):
    rm = make_rm(tmp_path)
    pf = PortfolioState(cash=1000.0, equity=1000.0, positions=[])
    v = rm.evaluate(prop("TMO", 1.0), pf, last_price=100)
    assert v.action == RiskAction.APPROVE


def test_pipeline_seeds_pending_from_queued_broker_orders(tmp_path):
    import yaml as _yaml
    from ai_investor.core.enums import Signal as _Sig
    from ai_investor.core.models import Order as _Order
    from ai_investor.orchestrator.pipeline import Pipeline
    from ai_investor.orchestrator.registry import Registry

    cfg = {"plugins": {"llm": "fake", "market_data": "fake", "news": "fake",
                       "broker": "fake", "notifier": "console", "macro": "fake"},
           "universe": {"watchlist": ["NVDA"]},
           "run": {"starting_cash": 10_000.0, "audit_dir": str(tmp_path / "runs"),
                   "slippage_bps": 0},
           "benchmark": {"ticker": "VOO"}}
    sp = tmp_path / "settings.yaml"
    sp.write_text(_yaml.safe_dump(cfg))
    rulesp = tmp_path / "rules.yaml"
    rulesp.write_text(_yaml.safe_dump(
        {"max_position_pct": 0.25, "min_cash_pct": 0.10, "max_open_positions": 8,
         "max_drawdown_halt_pct": 0.90, "min_confidence": 0.60}))

    reg = Registry(sp)
    price = reg.market_data.last_price("NVDA")
    # simulate a previous run's order still queued at the broker
    reg.broker.open_orders = lambda: [
        _Order(ticker="NVDA", signal=_Sig.BUY, quantity=8000 / price)]

    pipe = Pipeline(reg, rulesp)
    assert pipe._pending["cash"] > 7900  # queued $8k already counted
