"""Decision Agent (CEO). Phase 1: weighted synthesis in code with an LLM thesis.
Later phases move more reasoning into the model — same interface."""
from __future__ import annotations

from ai_investor.core.enums import Signal
from ai_investor.core.interfaces.providers import LLMProvider
from ai_investor.core.models import AgentReport, Objection, Rebuttal, TradeProposal


class DecisionAgent:
    name = "decision"

    def __init__(self, llm: LLMProvider, buy_threshold: float = 0.3, sell_threshold: float = -0.3):
        self.llm = llm
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def propose(self, ticker: str, reports: list[AgentReport], budget: float,
                last_price: float) -> TradeProposal:
        usable = [r for r in reports if r.confidence > 0]
        if not usable:
            return TradeProposal(ticker=ticker, signal=Signal.HOLD, quantity=0,
                                 confidence=0.0, thesis="no usable reports")
        weighted = sum(r.score * r.confidence for r in usable) / sum(r.confidence for r in usable)
        avg_conf = sum(r.confidence for r in usable) / len(usable)

        if weighted >= self.buy_threshold:
            signal, qty = Signal.BUY, round(budget / last_price, 4)
        elif weighted <= self.sell_threshold:
            signal, qty = Signal.SELL, 0.0  # sell sizing handled by portfolio in later phase
        else:
            signal, qty = Signal.HOLD, 0.0

        thesis = self.llm.complete(
            f"Ticker {ticker}, combined score {weighted:+.2f}. Reports: "
            + "; ".join(f"{r.agent}:{r.score:+.2f} ({r.summary})" for r in usable)
            + f". Write a 2-sentence thesis for {signal.value.upper()}."
        )
        return TradeProposal(ticker=ticker, signal=signal, quantity=qty,
                             confidence=round(avg_conf, 3), thesis=thesis.strip(),
                             cited_reports=[r.agent for r in usable])

    def rebut(self, proposal: TradeProposal, objections: list[Objection]) -> list[Rebuttal]:
        """One iteration only — no unbounded debate loops."""
        return [
            Rebuttal(objection_id=o.id,
                     response=self.llm.complete(
                         f"Objection to {proposal.signal.value} {proposal.ticker}: {o.text}. "
                         f"Thesis: {proposal.thesis}. Respond in one sentence."))
            for o in objections
        ]
