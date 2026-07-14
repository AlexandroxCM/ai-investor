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

    def __init__(self, rules_path: str | Path, state_path: str | Path = "runs/risk_state.json",
                 sector_of=None, price_of=None):
        self.rules = yaml.safe_load(Path(rules_path).read_text())
        self.state = RiskState(state_path)
        self.sector_of = sector_of   # callable ticker -> sector
        self.price_of = price_of     # callable ticker -> last price

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
                 last_price: float, pending: dict | None = None) -> RiskVerdict:
        """pending = {'cash': committed_this_cycle, 'sectors': {sector: cost}} —
        orders queued (e.g. after hours) aren't positions yet, but their cash
        and sector exposure are already spoken for."""
        pending = pending or {"cash": 0.0, "sectors": {}}
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
            max_cost_cash = (portfolio.cash - pending["cash"]
                             - self.rules["min_cash_pct"] * portfolio.equity)
            limits = {"max_position_pct": max_cost_position,
                      "min_cash_pct": max_cost_cash}

            max_sector = self.rules.get("max_sector_pct")
            if max_sector and self.sector_of and self.price_of:
                sector = self.sector_of(proposal.ticker)
                if sector not in ("ETF", "Unknown"):  # funds are already diversified
                    exposure = sum(
                        pos.quantity * self.price_of(pos.ticker)
                        for pos in portfolio.positions
                        if self.sector_of(pos.ticker) == sector)
                    exposure += pending["sectors"].get(sector, 0.0)
                    limits["max_sector_pct"] = max_sector * portfolio.equity - exposure

            binding_rule = min(limits, key=limits.get)
            allowed = max(0.0, limits[binding_rule])

            if cost > allowed and not triggered:
                if allowed <= 0:
                    triggered.append(binding_rule)
                else:
                    return RiskVerdict(
                        action=RiskAction.RESIZE,
                        approved_quantity=round(allowed / last_price, 4),
                        rules_triggered=[binding_rule],
                        note=f"resized from {proposal.quantity} to fit {binding_rule}")

        if triggered:
            return RiskVerdict(action=RiskAction.REJECT, approved_quantity=0,
                               rules_triggered=triggered)
        return RiskVerdict(action=RiskAction.APPROVE, approved_quantity=proposal.quantity)
