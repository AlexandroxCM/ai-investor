from pathlib import Path

import yaml

from ai_investor.agents.risk_manager import RiskManager
from ai_investor.core.enums import RiskAction, Signal
from ai_investor.core.models import PortfolioState, Position, TradeProposal

SECTORS = {"SCHW": "Financials", "COF": "Financials", "USB": "Financials",
           "NVDA": "Technology", "VOO": "ETF"}
PRICES = {"SCHW": 100.0, "COF": 200.0, "USB": 50.0, "NVDA": 500.0, "VOO": 690.0}


def make_rm(tmp_path, max_sector=0.40):
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.20,
             "min_confidence": 0.60, "max_sector_pct": max_sector}
    rp = tmp_path / "rules.yaml"
    rp.write_text(yaml.safe_dump(rules))
    return RiskManager(rp, state_path=tmp_path / "state.json",
                       sector_of=SECTORS.get, price_of=PRICES.get)


def prop(ticker, qty):
    return TradeProposal(ticker=ticker, signal=Signal.BUY, quantity=qty,
                         confidence=0.9, thesis="t")


def loaded_financials_portfolio():
    # $350 of financials in a $1000 portfolio (35% — near the 40% cap)
    return PortfolioState(
        cash=650.0, equity=1000.0,
        positions=[Position(ticker="SCHW", quantity=1.5, avg_cost=100),  # $150
                   Position(ticker="COF", quantity=1.0, avg_cost=200)])  # $200


def test_sector_cap_resizes_concentrated_buy(tmp_path):
    rm = make_rm(tmp_path)
    # wants $150 more financials; only $50 of sector headroom left
    v = rm.evaluate(prop("USB", 3.0), loaded_financials_portfolio(), last_price=50)
    assert v.action == RiskAction.RESIZE
    assert v.rules_triggered == ["max_sector_pct"]
    assert v.approved_quantity * 50 <= 50 + 1e-6


def test_sector_cap_rejects_when_no_headroom(tmp_path):
    rm = make_rm(tmp_path, max_sector=0.30)  # already over 30% financials
    v = rm.evaluate(prop("USB", 1.0), loaded_financials_portfolio(), last_price=50)
    assert v.action == RiskAction.REJECT
    assert "max_sector_pct" in v.rules_triggered


def test_other_sectors_unaffected(tmp_path):
    rm = make_rm(tmp_path)
    v = rm.evaluate(prop("NVDA", 0.2), loaded_financials_portfolio(), last_price=500)
    assert v.action == RiskAction.APPROVE


def test_etfs_exempt_from_sector_cap(tmp_path):
    rm = make_rm(tmp_path)
    v = rm.evaluate(prop("VOO", 0.2), loaded_financials_portfolio(), last_price=690)
    assert v.action == RiskAction.APPROVE


def test_rule_skipped_when_not_configured(tmp_path):
    rules = {"max_position_pct": 0.25, "min_cash_pct": 0.10,
             "max_open_positions": 8, "max_drawdown_halt_pct": 0.20,
             "min_confidence": 0.60}  # no max_sector_pct
    rp = tmp_path / "rules.yaml"
    rp.write_text(yaml.safe_dump(rules))
    rm = RiskManager(rp, state_path=tmp_path / "s.json")
    v = rm.evaluate(prop("USB", 1.0), loaded_financials_portfolio(), last_price=50)
    assert v.action == RiskAction.APPROVE
