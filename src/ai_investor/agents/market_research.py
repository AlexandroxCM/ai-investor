"""Market Research Agent: one focused pre-market pass over the whole
universe. Pure-code regime metrics (breadth, trend, volatility) classified
risk-on / neutral / risk-off, plus an LLM-written briefing. Runs at 9:15am
ET; the afternoon cycle feeds the result to the Decision Agent."""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from ai_investor.core.interfaces.providers import LLMProvider, MarketDataProvider
from ai_investor.core.models import AgentReport

REGIME_SCORE = {"risk-on": 0.3, "neutral": 0.0, "risk-off": -0.4}


class MarketResearchAgent:
    name = "regime"

    def __init__(self, data: MarketDataProvider, llm: LLMProvider,
                 universe: list[str], index_ticker: str = "SPY"):
        self.data = data
        self.llm = llm
        self.universe = universe
        self.index_ticker = index_ticker

    def compute_metrics(self) -> dict:
        all_bars = self.data.get_bars_bulk(self.universe, lookback_days=40)
        above_ma = total = 0
        for bars in all_bars.values():
            closes = [b.close for b in bars]
            if len(closes) < 30:
                continue
            total += 1
            if closes[-1] > sum(closes[-30:]) / 30:
                above_ma += 1
        breadth = above_ma / total if total else 0.5

        idx = self.data.get_bars(self.index_ticker, lookback_days=30)
        closes = [b.close for b in idx]
        trend_20d = closes[-1] / closes[-21] - 1 if len(closes) >= 21 else 0.0
        rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        vol_annual = statistics.pstdev(rets) * (252 ** 0.5) if len(rets) > 5 else 0.0

        if breadth >= 0.55 and trend_20d > 0 and vol_annual < 0.25:
            regime = "risk-on"
        elif breadth <= 0.40 or trend_20d < -0.03 or vol_annual > 0.35:
            regime = "risk-off"
        else:
            regime = "neutral"
        return {"breadth": round(breadth, 3), "trend_20d": round(trend_20d, 4),
                "vol_annual": round(vol_annual, 3), "regime": regime,
                "universe_size": total}

    def briefing(self, macro_summary: str = "") -> dict:
        m = self.compute_metrics()
        try:
            text = self.llm.complete(
                "Write a 60-word pre-market briefing for an automated investor. "
                f"Market regime: {m['regime']}. Breadth: {m['breadth']:.0%} of "
                f"{m['universe_size']} large caps above their 30-day average. "
                f"Index 20-day trend: {m['trend_20d']:+.1%}. Annualized "
                f"volatility: {m['vol_annual']:.0%}. Macro: {macro_summary or 'n/a'}. "
                "State what today's stance should be and the main risk. No hype.")
        except Exception as e:
            text = f"(briefing unavailable: {type(e).__name__}) regime={m['regime']}"
        return {"date": datetime.now(timezone.utc).date().isoformat(),
                "metrics": m, "briefing": text.strip()}

    @staticmethod
    def save(briefing: dict, audit_dir: Path) -> Path:
        path = Path(audit_dir) / f"briefing-{briefing['date']}.json"
        path.write_text(json.dumps(briefing, indent=2))
        return path

    @staticmethod
    def load_today(audit_dir: Path) -> dict | None:
        path = Path(audit_dir) / (
            f"briefing-{datetime.now(timezone.utc).date().isoformat()}.json")
        if not path.exists():
            return None
        return json.loads(path.read_text())

    @staticmethod
    def as_report(briefing: dict, ticker: str) -> AgentReport:
        m = briefing["metrics"]
        return AgentReport(
            agent="regime", ticker=ticker,
            score=REGIME_SCORE.get(m["regime"], 0.0), confidence=0.5,
            summary=f"{m['regime']}: breadth {m['breadth']:.0%}, "
                    f"trend {m['trend_20d']:+.1%}, vol {m['vol_annual']:.0%}",
            evidence=[briefing["briefing"][:300]])
