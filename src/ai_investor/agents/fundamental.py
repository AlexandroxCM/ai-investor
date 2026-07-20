"""Pure code — no LLM, no hallucinated ratios. Scores value, growth, and
financial health from API-sourced metrics with explicit thresholds. ETFs
abstain (a fund has no single-company fundamentals)."""
from __future__ import annotations

from ai_investor.agents.base import ResearchAgent
from ai_investor.core.interfaces.providers import (FundamentalsProvider,
                                                   MarketDataProvider)
from ai_investor.core.models import AgentReport


class FundamentalAgent(ResearchAgent):
    name = "fundamental"

    def __init__(self, fundamentals: FundamentalsProvider,
                 market_data: MarketDataProvider):
        self.fundamentals = fundamentals
        self.market_data = market_data

    def run(self, ticker: str) -> AgentReport:
        if self.market_data.sector(ticker) == "ETF":
            return AgentReport(agent=self.name, ticker=ticker, score=0.0,
                               confidence=0.0,
                               summary="ETF — no single-company fundamentals")
        m = self.fundamentals.get_metrics(ticker)
        if len(m) < 3:
            return AgentReport(agent=self.name, ticker=ticker, score=0.0,
                               confidence=0.0, summary="insufficient fundamental data")

        score, evidence = 0.0, []

        growth = m.get("revenue_growth")
        if growth is not None:
            if growth > 0.15:
                score += 0.30; evidence.append(f"revenue growing {growth:+.0%}")
            elif growth > 0.05:
                score += 0.10; evidence.append(f"revenue growth modest {growth:+.0%}")
            elif growth < 0:
                score -= 0.30; evidence.append(f"revenue SHRINKING {growth:+.0%}")

        margin = m.get("profit_margin")
        if margin is not None:
            if margin > 0.15:
                score += 0.15; evidence.append(f"strong margins {margin:.0%}")
            elif margin < 0:
                score -= 0.25; evidence.append("unprofitable")

        pe = m.get("forward_pe")
        if pe is not None and pe > 0:
            # crude PEG: forward PE relative to growth
            if growth and growth > 0 and pe / (growth * 100) < 1.2:
                score += 0.20; evidence.append(f"cheap for its growth (fPE {pe:.0f})")
            elif pe > 45:
                score -= 0.20; evidence.append(f"expensive (fPE {pe:.0f})")
            elif pe < 16:
                score += 0.10; evidence.append(f"value territory (fPE {pe:.0f})")

        roe = m.get("roe")
        if roe is not None:
            if roe >= 0.15:
                score += 0.15; evidence.append(f"strong ROE {roe:.0%}")
            elif roe < 0:
                score -= 0.15; evidence.append(f"negative ROE {roe:.0%}")

        op = m.get("operating_margin")
        if op is not None:
            if op >= 0.15:
                score += 0.10; evidence.append(f"efficient ops (margin {op:.0%})")
            elif op < 0:
                score -= 0.15; evidence.append("operating at a loss")

        dte = m.get("debt_to_equity")
        if dte is not None and dte > 2.0:
            score -= 0.15; evidence.append(f"heavy debt (D/E {dte:.1f})")

        fcf = m.get("free_cash_flow")
        if fcf is not None:
            if fcf > 0:
                score += 0.10; evidence.append("positive free cash flow")
            else:
                score -= 0.15; evidence.append("burning cash")

        score = max(-1.0, min(1.0, score))
        confidence = min(0.75, 0.15 * len(m))
        return AgentReport(agent=self.name, ticker=ticker,
                           score=round(score, 3), confidence=round(confidence, 2),
                           summary="; ".join(evidence) or "neutral fundamentals",
                           evidence=[f"{k}={v}" for k, v in m.items()])
