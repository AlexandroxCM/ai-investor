"""Pure code. Reads risk_rules.yaml only. Its verdict is final —
no agent output can override it. Never make this an LLM.

Kill switch: tracks a persistent equity high-water mark. If drawdown from
peak exceeds max_drawdown_halt_pct, ALL trading halts until a human runs
scripts/reset_kill_switch.py. Halting is automatic; resuming never is."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai_investor.core.enums import RiskAction, Signal
from ai_investor.core.models import PortfolioState, RiskVerdict, TradeProposal


class RiskState:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.high_water_mark: float = data.get("high_water_mark", 0.0)
        self.halted: bool = data.get("halted", False)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"high_water_mark": self.high_water_mark, "halted": self.halted}, indent=2))


class RiskManager:
    name = "risk"

    def __init__(self, rules_path: str | Path, state_path: str | Path = "runs/risk_state.json"):
        self.rules = yaml.safe_load(Path(rules_path).read_text())
        self.state = RiskState(state_path)

    def _check_kill_switch(self, portfolio: PortfolioState) -> bool:
        """Update high-water mark; return True if trading must halt."""
        if portfolio.equity > self.state.high_water_mark:
            self.state.high_water_mark = portfolio.equity
        hwm = self.state.high_water_mark
        if hwm > 0:
            drawdown = 1 - portfolio.equity / hwm
            if drawdown >= self.rules["max_drawdown_halt_pct"]:
                self.state.halted = True
        self.state.save()
        return self.state.halted

    def evaluate(self, proposal: TradeProposal, portfolio: PortfolioState,
                 last_price: float) -> RiskVerdict:
        if self._check_kill_switch(portfolio):
            return RiskVerdict(
                action=RiskAction.REJECT, approved_quantity=0,
                rules_triggered=["kill_switch"],
                note=f"HALTED: drawdown limit hit (peak ${self.state.high_water_mark:.2f}, "
                     f"now ${portfolio.equity:.2f}). Manual reset required.")

        triggered: list[str] = []

        if proposal.signal == Signal.HOLD:
            return RiskVerdict(action=RiskAction.APPROVE, approved_quantity=0)

        if proposal.confidence < self.rules["min_confidence"]:
            triggered.append("min_confidence")

        if proposal.signal == Signal.BUY:
            if len(portfolio.positions) >= self.rules["max_open_positions"]:
                triggered.append("max_open_positions")

            cost = proposal.quantity * last_price
            max_cost_position = self.rules["max_position_pct"] * portfolio.equity
            max_cost_cash = portfolio.cash - self.rules["min_cash_pct"] * portfolio.equity
            allowed = max(0.0, min(max_cost_position, max_cost_cash))

            if cost > allowed and not triggered:
                if allowed <= 0:
                    triggered.append("min_cash_pct")
                else:
                    return RiskVerdict(
                        action=RiskAction.RESIZE,
                        approved_quantity=round(allowed / last_price, 4),
                        rules_triggered=["max_position_pct"],
                        note=f"resized from {proposal.quantity} to fit limits")

        if triggered:
            return RiskVerdict(action=RiskAction.REJECT, approved_quantity=0,
                               rules_triggered=triggered)
        return RiskVerdict(action=RiskAction.APPROVE, approved_quantity=proposal.quantity)
