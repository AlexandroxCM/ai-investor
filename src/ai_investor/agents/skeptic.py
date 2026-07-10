from __future__ import annotations

from ai_investor.core.enums import Signal
from ai_investor.core.interfaces.providers import LLMProvider
from ai_investor.core.models import AgentReport, Objection, TradeProposal


class SkepticAgent:
    name = "skeptic"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def challenge(self, proposal: TradeProposal, reports: list[AgentReport]) -> list[Objection]:
        if proposal.signal == Signal.HOLD:
            return []
        raw = self.llm.complete(
            f"Play devil's advocate. Proposal: {proposal.signal.value} {proposal.ticker}, "
            f"thesis: {proposal.thesis}. Reports: "
            + "; ".join(f"{r.agent}:{r.summary}" for r in reports)
            + ". List the 2 strongest reasons NOT to do this, one per line."
        )
        lines = [ln.strip("- ").strip() for ln in raw.splitlines() if ln.strip()]
        return [Objection(id=f"obj-{i+1}", text=t) for i, t in enumerate(lines[:3])]
