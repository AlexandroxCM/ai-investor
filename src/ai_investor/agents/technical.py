"""Pure code — no LLM. Full indicator suite from the original spec:
MA crossover, RSI(14), MACD histogram, Bollinger position, volume trend.
Each votes a small amount; no single indicator can dominate."""
from __future__ import annotations

from ai_investor.agents.base import ResearchAgent
from ai_investor.core.interfaces.providers import MarketDataProvider
from ai_investor.core.models import AgentReport


def ema(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes: list[float], period: int = 14) -> float:
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


class TechnicalAgent(ResearchAgent):
    name = "technical"

    def __init__(self, data: MarketDataProvider, fast: int = 10, slow: int = 30):
        self.data = data
        self.fast = fast
        self.slow = slow

    def run(self, ticker: str) -> AgentReport:
        bars = self.data.get_bars(ticker, lookback_days=60)
        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]
        if len(closes) < 35:
            return AgentReport(agent=self.name, ticker=ticker, score=0.0,
                               confidence=0.0, summary="insufficient data")

        score, evidence = 0.0, []

        fast_ma = sum(closes[-self.fast:]) / self.fast
        slow_ma = sum(closes[-self.slow:]) / self.slow
        spread = (fast_ma - slow_ma) / slow_ma
        score += max(-0.3, min(0.3, spread * 10))
        evidence.append(f"MA{self.fast}/{self.slow} spread {spread:+.2%}")

        r = rsi(closes)
        if r > 70:
            score -= 0.20; evidence.append(f"RSI overbought ({r:.0f})")
        elif r < 30:
            score += 0.20; evidence.append(f"RSI oversold ({r:.0f})")
        else:
            evidence.append(f"RSI neutral ({r:.0f})")

        ema12, ema26 = ema(closes, 12), ema(closes, 26)
        macd_line = [a - b for a, b in zip(ema12, ema26)]
        signal_line = ema(macd_line, 9)
        hist = macd_line[-1] - signal_line[-1]
        hist_pct = hist / closes[-1]
        score += max(-0.2, min(0.2, hist_pct * 40))
        evidence.append(f"MACD histogram {'positive' if hist > 0 else 'negative'}")

        window = closes[-20:]
        mid = sum(window) / len(window)
        var = sum((c - mid) ** 2 for c in window) / len(window)
        band = 2 * var ** 0.5
        if band > 0:
            b_pos = (closes[-1] - mid) / band  # -1 lower band .. +1 upper band
            if b_pos > 1.0:
                score -= 0.15; evidence.append("above upper Bollinger band")
            elif b_pos < -1.0:
                score += 0.15; evidence.append("below lower Bollinger band")

        recent_vol = sum(volumes[-5:]) / 5
        base_vol = sum(volumes[-30:]) / 30
        if base_vol > 0 and recent_vol / base_vol > 1.5:
            direction = 1 if closes[-1] > closes[-6] else -1
            score += 0.10 * direction
            evidence.append(f"volume surge {'confirming' if direction > 0 else 'on decline'}")

        score = max(-1.0, min(1.0, score))
        return AgentReport(agent=self.name, ticker=ticker, score=round(score, 3),
                           confidence=0.7,
                           summary="; ".join(evidence),
                           evidence=[f"close={closes[-1]:.2f}", f"rsi={r:.1f}",
                                     f"macd_hist={hist:.4f}"])
