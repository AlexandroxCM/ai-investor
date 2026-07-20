"""Pure-code screener: scans a broad universe cheaply (price data only, no
LLM calls) and returns the top candidates worth the expensive AI treatment.
Score = recent momentum + liquidity. Deliberately simple and explainable."""
from __future__ import annotations

from ai_investor.core.interfaces.providers import MarketDataProvider


class Screener:
    def __init__(self, data: MarketDataProvider, universe: list[str],
                 top_n: int = 15, min_price: float = 5.0,
                 min_dollar_volume: float = 5_000_000,
                 trend_gate: bool = False):
        self.trend_gate = trend_gate
        self.data = data
        self.universe = universe
        self.top_n = top_n
        self.min_price = min_price
        self.min_dollar_volume = min_dollar_volume

    def _score(self, ticker: str, bars=None) -> tuple[float, dict] | None:
        if bars is None:
            try:
                bars = self.data.get_bars(ticker, lookback_days=40)
            except Exception as e:
                print(f"[screener] {ticker} skipped: {e}")
                return None
        if len(bars) < 25:
            return None
        closes = [b.close for b in bars]
        price = closes[-1]
        if price < self.min_price:
            return None
        recent = bars[-10:]
        dollar_vol = sum(b.close * b.volume for b in recent) / len(recent)
        if dollar_vol < self.min_dollar_volume:
            return None
        momentum_20d = closes[-1] / closes[-21] - 1 if len(closes) >= 21 else 0.0
        # momentum drives ranking; liquidity is a gate, not a tiebreaker
        return momentum_20d, {"price": price, "momentum_20d": momentum_20d,
                              "avg_dollar_volume": dollar_vol}

    def top_candidates(self, always_include: list[str] | None = None) -> list[str]:
        """Rank the universe; always_include (e.g. current holdings) are
        appended so the pipeline never goes blind on an open position."""
        scored: list[tuple[float, str]] = []
        all_bars = self.data.get_bars_bulk(self.universe, lookback_days=40)
        for ticker in self.universe:
            if ticker not in all_bars:
                continue
            result = self._score(ticker, bars=all_bars[ticker])
            if result is not None:
                scored.append((result[0], ticker))
        scored.sort(reverse=True)
        ranked = [t for _, t in scored]
        if self.trend_gate and ranked:
            pre = ranked[: self.top_n * 3]
            deep = self.data.get_bars_bulk(pre, lookback_days=260)
            passing = [t for t in pre
                       if t in deep and passes_trend_template(deep[t])]
            if len(passing) < max(2, self.top_n // 2):
                print(f"[screener] trend gate strict today "
                      f"({len(passing)}/{len(pre)} pass) — topping up by rank")
                passing += [t for t in pre if t not in passing]
            ranked = passing
        picks = ranked[: self.top_n]
        for t in always_include or []:
            if t not in picks:
                picks.append(t)
        return picks


def passes_trend_template(bars) -> bool:
    """Minervini core tests: price above 150d & 200d MAs, 200d MA rising
    vs a month ago, and price within 25% of the 52-week high."""
    closes = [b.close for b in bars]
    if len(closes) < 220:
        return False
    price = closes[-1]
    ma150 = sum(closes[-150:]) / 150
    ma200 = sum(closes[-200:]) / 200
    ma200_month_ago = sum(closes[-221:-21]) / 200
    high_52w = max(closes)
    return (price > ma150 and price > ma200
            and ma200 > ma200_month_ago
            and price >= 0.75 * high_52w)
