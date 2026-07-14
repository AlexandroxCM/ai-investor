from pathlib import Path
from unittest.mock import MagicMock

import yaml

from ai_investor.agents.decision import DecisionAgent
from ai_investor.agents.risk_manager import RiskManager
from ai_investor.agents.skeptic import SkepticAgent
from ai_investor.core.enums import RiskAction, Signal
from ai_investor.core.models import (AgentReport, Objection, PortfolioState,
                                     Position, Rebuttal, TradeProposal)
from ai_investor.plugins.fakes import FakeLLM


def rules_file(tmp_path, extra=None):
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.20,
             "min_confidence": 0.60}
    rules.update(extra or {})
    rp = tmp_path / "rules.yaml"
    rp.write_text(yaml.safe_dump(rules))
    return rp


def bearish_reports(ticker="NVDA"):
    return [AgentReport(agent="technical", ticker=ticker, score=-0.8,
                        confidence=0.9, summary="breakdown"),
            AgentReport(agent="news", ticker=ticker, score=-0.6,
                        confidence=0.8, summary="bad quarter")]


def test_decision_sells_full_position_when_bearish():
    d = DecisionAgent(FakeLLM())
    prop = d.propose("NVDA", bearish_reports(), budget=100, last_price=100,
                     held_qty=3.5)
    assert prop.signal == Signal.SELL
    assert prop.quantity == 3.5


def test_decision_holds_when_bearish_but_nothing_held():
    d = DecisionAgent(FakeLLM())
    prop = d.propose("NVDA", bearish_reports(), budget=100, last_price=100,
                     held_qty=0.0)
    assert prop.signal == Signal.HOLD


def test_risk_rejects_selling_unheld_ticker(tmp_path):
    rm = RiskManager(rules_file(tmp_path), state_path=tmp_path / "s.json")
    pf = PortfolioState(cash=1000, equity=1000, positions=[])
    prop = TradeProposal(ticker="NVDA", signal=Signal.SELL, quantity=1,
                         confidence=0.9, thesis="t")
    v = rm.evaluate(prop, pf, last_price=100)
    assert v.action == RiskAction.REJECT
    assert "no_position" in v.rules_triggered


def test_risk_caps_oversell_at_held_quantity(tmp_path):
    rm = RiskManager(rules_file(tmp_path), state_path=tmp_path / "s.json")
    pf = PortfolioState(cash=0, equity=500,
                        positions=[Position(ticker="NVDA", quantity=2, avg_cost=100)])
    prop = TradeProposal(ticker="NVDA", signal=Signal.SELL, quantity=5,
                         confidence=0.9, thesis="t")
    v = rm.evaluate(prop, pf, last_price=100)
    assert v.action == RiskAction.RESIZE
    assert v.approved_quantity == 2


def test_cooldown_blocks_rebuy(tmp_path):
    rm = RiskManager(rules_file(tmp_path, {"cooldown_days": 3}),
                     state_path=tmp_path / "s.json")
    rm.record_trade("NVDA")
    pf = PortfolioState(cash=1000, equity=1000, positions=[])
    prop = TradeProposal(ticker="NVDA", signal=Signal.BUY, quantity=1,
                         confidence=0.9, thesis="t")
    v = rm.evaluate(prop, pf, last_price=10)
    assert v.action == RiskAction.REJECT
    assert "cooldown" in v.rules_triggered
    # other tickers unaffected
    v2 = rm.evaluate(TradeProposal(ticker="AAPL", signal=Signal.BUY, quantity=1,
                                   confidence=0.9, thesis="t"), pf, last_price=10)
    assert v2.action == RiskAction.APPROVE


def test_skeptic_judge_flags_sustained_objections():
    llm = MagicMock()
    llm.complete.return_value = "obj-1: SUSTAIN\nobj-2: WITHDRAWN"
    sk = SkepticAgent(llm)
    prop = TradeProposal(ticker="NVDA", signal=Signal.BUY, quantity=1,
                         confidence=0.8, thesis="t")
    objections = [Objection(id="obj-1", text="a"), Objection(id="obj-2", text="b")]
    rebuttals = [Rebuttal(objection_id="obj-1", response="r1"),
                 Rebuttal(objection_id="obj-2", response="r2")]
    assert sk.judge(prop, objections, rebuttals) == ["obj-1"]


def test_dead_skeptic_never_crashes_cycle(tmp_path):
    import yaml as _yaml
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
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.90,
             "min_confidence": 0.60}
    rp = tmp_path / "rules.yaml"
    rp.write_text(_yaml.safe_dump(rules))

    reg = Registry(sp)
    pipe = Pipeline(reg, rp)
    broken = MagicMock()
    broken.complete.side_effect = RuntimeError("LLM rate-limit retries exhausted")
    pipe.skeptic = SkepticAgent(broken)

    rec = pipe.run_cycle("NVDA", budget=500)  # must complete despite dead judge
    assert rec.verdict is not None
    assert any("skeptic unavailable" in n for n in rec.notes)
