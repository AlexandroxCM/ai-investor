"""Pure code — no LLM. Reads standard FRED series and scores the macro
climate with explicit, explainable rules. Market-wide: computed once per
cycle and attached to every ticker's report set."""
from __future__ import annotations

from ai_investor.core.interfaces.providers import MacroProvider
from ai_investor.core.models import AgentReport

SERIES = {
    "yield_curve": "T10Y2Y",    # 10yr minus 2yr spread (daily)
    "inflation": "CPIAUCSL",    # CPI index (monthly)
    "unemployment": "UNRATE",   # unemployment rate (monthly)
    "fed_funds": "FEDFUNDS",    # policy rate (monthly)
}


class MacroAgent:
    name = "macro"

    def __init__(self, macro: MacroProvider):
        self.macro = macro
        self._cached: AgentReport | None = None

    def run_market(self) -> AgentReport:
        """Compute once, reuse for every ticker in the same process."""
        if self._cached is not None:
            return self._cached

        score, evidence = 0.0, []

        curve = self.macro.get_series(SERIES["yield_curve"], limit=5)
        if curve:
            if curve[-1] < 0:
                score -= 0.4
                evidence.append(f"yield curve inverted ({curve[-1]:+.2f}) — recession signal")
            else:
                score += 0.1
                evidence.append(f"yield curve normal ({curve[-1]:+.2f})")

        cpi = self.macro.get_series(SERIES["inflation"], limit=13)
        if len(cpi) >= 13:
            yoy = cpi[-1] / cpi[-13] - 1
            if yoy > 0.04:
                score -= 0.3
                evidence.append(f"inflation hot ({yoy:.1%} YoY)")
            elif yoy < 0.03:
                score += 0.2
                evidence.append(f"inflation contained ({yoy:.1%} YoY)")
            else:
                evidence.append(f"inflation elevated ({yoy:.1%} YoY)")

        unrate = self.macro.get_series(SERIES["unemployment"], limit=4)
        if len(unrate) >= 4:
            delta = unrate[-1] - unrate[0]
            if delta > 0.3:
                score -= 0.3
                evidence.append(f"unemployment rising ({unrate[0]:.1f}% -> {unrate[-1]:.1f}%)")
            else:
                score += 0.1
                evidence.append(f"unemployment stable ({unrate[-1]:.1f}%)")

        ff = self.macro.get_series(SERIES["fed_funds"], limit=7)
        if len(ff) >= 7:
            if ff[-1] < ff[0] - 0.1:
                score += 0.2
                evidence.append(f"Fed easing ({ff[0]:.2f}% -> {ff[-1]:.2f}%)")
            elif ff[-1] > ff[0] + 0.1:
                score -= 0.1
                evidence.append(f"Fed tightening ({ff[0]:.2f}% -> {ff[-1]:.2f}%)")
            else:
                evidence.append(f"Fed on hold ({ff[-1]:.2f}%)")

        score = max(-1.0, min(1.0, score))
        self._cached = AgentReport(
            agent=self.name, ticker="MARKET", score=round(score, 3),
            confidence=0.6 if evidence else 0.0,
            summary="; ".join(evidence) or "no macro data available",
            evidence=evidence)
        return self._cached
