"""Pure code — no LLM. Deterministic, unit-testable, free."""
from __future__ import annotations

from ai_investor.agents.base import ResearchAgent
from ai_investor.core.interfaces.providers import MarketDataProvider
from ai_investor.core.models import AgentReport


class TechnicalAgent(ResearchAgent):
    name = "technical"

    def __init__(self, data: MarketDataProvider, fast: int = 10, slow: int = 30):
        self.data = data
        self.fast = fast
        self.slow = slow

    def run(self, ticker: str) -> AgentReport:
        bars = self.data.get_bars(ticker, lookback_days=self.slow + 10)
        closes = [b.close for b in bars]
        if len(closes) < self.slow:
            return AgentReport(agent=self.name, ticker=ticker, score=0.0,
                               confidence=0.0, summary="insufficient data")
        fast_ma = sum(closes[-self.fast:]) / self.fast
        slow_ma = sum(closes[-self.slow:]) / self.slow
        spread = (fast_ma - slow_ma) / slow_ma
        score = max(-1.0, min(1.0, spread * 20))  # normalize to [-1, 1]
        return AgentReport(
            agent=self.name, ticker=ticker, score=round(score, 3),
            confidence=0.7,
            summary=f"MA{self.fast}={fast_ma:.2f} vs MA{self.slow}={slow_ma:.2f} ({spread:+.2%})",
            evidence=[f"fast_ma={fast_ma:.4f}", f"slow_ma={slow_ma:.4f}"],
        )
