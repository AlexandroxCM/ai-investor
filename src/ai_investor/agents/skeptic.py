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

    def judge(self, proposal: TradeProposal, objections: list[Objection],
              rebuttals) -> list[str]:
        """Final verdict: did the rebuttals actually answer the objections?
        Returns IDs of SUSTAINED objections — each one docks confidence.
        This is the 'is this actually a good idea?' check, ideally run on a
        DIFFERENT model than the one that wrote the thesis."""
        if not objections:
            return []
        pairs = []
        rebuttal_map = {r.objection_id: r.response for r in rebuttals}
        for o in objections:
            pairs.append(f"{o.id}: OBJECTION: {o.text} REBUTTAL: "
                         f"{rebuttal_map.get(o.id, '(none given)')}")
        raw = self.llm.complete(
            f"You are the final judge on a proposed trade: {proposal.signal.value} "
            f"{proposal.ticker}. For each objection below, decide if the rebuttal "
            f"genuinely answers it (WITHDRAWN) or merely restates the thesis "
            f"(SUSTAIN). Reply one line per objection: '<id>: SUSTAIN' or "
            f"'<id>: WITHDRAWN'.\n" + "\n".join(pairs))
        sustained = []
        for line in raw.splitlines():
            if "SUSTAIN" in line.upper():
                for o in objections:
                    if o.id in line:
                        sustained.append(o.id)
        return sustained
