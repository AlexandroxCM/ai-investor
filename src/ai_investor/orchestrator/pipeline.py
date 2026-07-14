"""One full cycle: research -> decide -> skeptic -> rebut -> risk -> execute -> audit.
Every step lands in a RunRecord written to disk (SQLite replaces JSON next)."""
from __future__ import annotations

import uuid
from pathlib import Path

from ai_investor.agents.decision import DecisionAgent
from ai_investor.agents.macro import MacroAgent
from ai_investor.agents.news import NewsAgent
from ai_investor.agents.risk_manager import RiskManager
from ai_investor.agents.skeptic import SkepticAgent
from ai_investor.agents.technical import TechnicalAgent
from ai_investor.core.enums import RiskAction, Signal
from ai_investor.core.models import Order, RunRecord
from ai_investor.audit.store import AuditStore
from ai_investor.orchestrator.registry import Registry


class Pipeline:
    def __init__(self, registry: Registry, risk_rules_path: str | Path):
        self.reg = registry
        self.research = [
            TechnicalAgent(registry.market_data),
            NewsAgent(registry.llm, registry.news),
        ]
        self.macro = MacroAgent(registry.macro)
        self.decision = DecisionAgent(registry.llm)
        self.skeptic = SkepticAgent(registry.llm)
        self.audit_dir = Path(registry.settings["run"]["audit_dir"])
        self.audit_dir.mkdir(exist_ok=True)
        self.risk = RiskManager(risk_rules_path,
                                state_path=self.audit_dir / "risk_state.json",
                                sector_of=registry.market_data.sector,
                                price_of=registry.market_data.last_price)
        self.store = AuditStore(self.audit_dir / "audit.db")
        # orders committed this cycle but not yet filled (e.g. queued overnight)
        self._pending = {"cash": 0.0, "sectors": {}}

    def run_cycle(self, ticker: str, budget: float,
                  strategy: str = "momentum") -> RunRecord:
        rec = RunRecord(run_id=f"{ticker}-{uuid.uuid4().hex[:8]}",
                        strategy=strategy)

        rec.reports = [agent.run(ticker) for agent in self.research]
        rec.reports.append(
            self.macro.run_market().model_copy(update={"ticker": ticker}))

        last_price = self.reg.market_data.last_price(ticker)
        rec.proposal = self.decision.propose(ticker, rec.reports, budget, last_price)

        rec.objections = self.skeptic.challenge(rec.proposal, rec.reports)
        if rec.objections:
            rec.rebuttals = self.decision.rebut(rec.proposal, rec.objections)

        portfolio = self.reg.broker.portfolio()
        rec.verdict = self.risk.evaluate(rec.proposal, portfolio, last_price,
                                         pending=self._pending)

        if (rec.verdict.action in (RiskAction.APPROVE, RiskAction.RESIZE)
                and rec.proposal.signal != Signal.HOLD
                and rec.verdict.approved_quantity > 0):
            order = Order(ticker=ticker, signal=rec.proposal.signal,
                          quantity=rec.verdict.approved_quantity,
                          client_order_id=rec.run_id)
            rec.order = self.reg.broker.submit(order)
            if rec.order.status.value != "rejected":
                cost = rec.order.quantity * last_price
                self._pending["cash"] += cost
                sector = self.reg.market_data.sector(ticker)
                self._pending["sectors"][sector] = (
                    self._pending["sectors"].get(sector, 0.0) + cost)
        else:
            rec.notes.append(f"no execution: verdict={rec.verdict.action.value}, "
                             f"rules={rec.verdict.rules_triggered}")

        rec.portfolio_after = self.reg.broker.portfolio()
        rec.benchmark_value = self.reg.benchmark.value()
        self._audit(rec)
        return rec

    def _audit(self, rec: RunRecord) -> None:
        # human-readable JSON per run + queryable SQLite row
        (self.audit_dir / f"{rec.run_id}.json").write_text(rec.model_dump_json(indent=2))
        self.store.save(rec)
