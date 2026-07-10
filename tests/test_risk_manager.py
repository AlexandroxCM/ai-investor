from pathlib import Path

from ai_investor.agents.risk_manager import RiskManager
from ai_investor.core.enums import RiskAction, Signal
from ai_investor.core.models import PortfolioState, TradeProposal

RULES = Path(__file__).parent.parent / "config" / "risk_rules.yaml"


def make_proposal(**kw):
    base = dict(ticker="TEST", signal=Signal.BUY, quantity=10,
                confidence=0.9, thesis="t")
    base.update(kw)
    return TradeProposal(**base)


def test_rejects_low_confidence(tmp_path):
    rm = RiskManager(RULES, state_path=tmp_path / "s.json")
    pf = PortfolioState(cash=1000, equity=1000)
    v = rm.evaluate(make_proposal(confidence=0.1), pf, last_price=10)
    assert v.action == RiskAction.REJECT
    assert "min_confidence" in v.rules_triggered


def test_resizes_oversized_position(tmp_path):
    rm = RiskManager(RULES, state_path=tmp_path / "s.json")
    pf = PortfolioState(cash=1000, equity=1000)
    # 10 shares @ $50 = $500 = 50% of equity; limit is 25%
    v = rm.evaluate(make_proposal(quantity=10), pf, last_price=50)
    assert v.action == RiskAction.RESIZE
    assert v.approved_quantity * 50 <= 0.25 * pf.equity + 1e-6


def test_approves_within_limits(tmp_path):
    rm = RiskManager(RULES, state_path=tmp_path / "s.json")
    pf = PortfolioState(cash=1000, equity=1000)
    v = rm.evaluate(make_proposal(quantity=10), pf, last_price=10)  # $100 = 10%
    assert v.action == RiskAction.APPROVE
    assert v.approved_quantity == 10


def test_hold_always_approved(tmp_path):
    rm = RiskManager(RULES, state_path=tmp_path / "s.json")
    pf = PortfolioState(cash=0, equity=0)
    v = rm.evaluate(make_proposal(signal=Signal.HOLD, quantity=0), pf, last_price=10)
    assert v.action == RiskAction.APPROVE
