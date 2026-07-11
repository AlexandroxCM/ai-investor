"""Deterministic test doubles. The whole pipeline runs on these at $0 —
CI, unit tests, and Phase 1 demos never touch a network."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from ai_investor.core.enums import OrderStatus, Signal
from ai_investor.core.interfaces.providers import (Broker, LLMProvider, MacroProvider,
                                                   MarketDataProvider, NewsProvider)
from ai_investor.core.models import Article, Bar, Order, PortfolioState, Position


class FakeLLM(LLMProvider):
    def complete(self, prompt: str, system: str = "") -> str:
        if "news analyst" in system:
            return json.dumps({"sentiment": 0.5, "confidence": 0.8,
                               "summary": "fake: mildly positive coverage"})
        if "devil's advocate" in prompt:
            return "Valuation already prices in the good news.\nMomentum can reverse on macro shifts."
        return "Fake thesis: indicators align modestly positive. Position sized conservatively."


class FakeMarketData(MarketDataProvider):
    """Seeded random walk — identical output every run for a given ticker."""

    def get_bars(self, ticker: str, lookback_days: int) -> list[Bar]:
        rng = random.Random(ticker)  # deterministic per ticker
        price = 100.0 + rng.random() * 400
        start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        bars = []
        for i in range(lookback_days):
            drift = rng.uniform(-0.02, 0.025)
            o = price
            price = max(1.0, price * (1 + drift))
            bars.append(Bar(ticker=ticker, date=start + timedelta(days=i),
                            open=round(o, 2), high=round(max(o, price) * 1.01, 2),
                            low=round(min(o, price) * 0.99, 2), close=round(price, 2),
                            volume=rng.randint(1_000_000, 50_000_000)))
        return bars

    def last_price(self, ticker: str) -> float:
        return self.get_bars(ticker, 40)[-1].close

    def dividend_yield(self, ticker: str) -> float:
        yields = {"VOO": 0.013, "QQQ": 0.006, "AAPL": 0.005, "MSFT": 0.007}
        return yields.get(ticker, 0.0)


class FakeNews(NewsProvider):
    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]:
        now = datetime.now(timezone.utc)
        return [Article(ticker=ticker, headline=f"{ticker} beats expectations",
                        body="Fake article body about strong results.", published=now)][:limit]


class FakeBroker(Broker):
    """Minimal paper simulator: instant fills at provided price. This class
    grows into the Phase 3 backtest fill engine."""

    def __init__(self, data: MarketDataProvider, starting_cash: float = 1000.0,
                 slippage_bps: float = 5.0):
        self.data = data
        self.cash = starting_cash
        self.slippage_bps = slippage_bps  # always against you: buy higher, sell lower
        self.positions: dict[str, Position] = {}

    def deposit(self, amount: float) -> None:
        self.cash += amount

    def submit(self, order: Order) -> Order:
        mid = self.data.last_price(order.ticker)
        slip = self.slippage_bps / 10_000
        price = mid * (1 + slip) if order.signal == Signal.BUY else mid * (1 - slip)
        cost = order.quantity * price
        if order.signal == Signal.BUY:
            if cost > self.cash:
                order.status = OrderStatus.REJECTED
                return order
            self.cash -= cost
            pos = self.positions.get(order.ticker)
            if pos:
                total_qty = pos.quantity + order.quantity
                pos.avg_cost = (pos.avg_cost * pos.quantity + cost) / total_qty
                pos.quantity = total_qty
            else:
                self.positions[order.ticker] = Position(
                    ticker=order.ticker, quantity=order.quantity, avg_cost=price)
        elif order.signal == Signal.SELL:
            pos = self.positions.get(order.ticker)
            if not pos or pos.quantity < order.quantity:
                order.status = OrderStatus.REJECTED
                return order
            self.cash += cost
            pos.quantity -= order.quantity
            if pos.quantity <= 1e-9:
                del self.positions[order.ticker]
        order.status = OrderStatus.FILLED
        order.fill_price = price
        order.filled_at = datetime.now(timezone.utc)
        return order

    def apply_dividends(self, period_days: int) -> float:
        """Credit cash dividends accrued over period_days on all holdings."""
        total = 0.0
        for pos in self.positions.values():
            y = self.data.dividend_yield(pos.ticker)
            total += pos.quantity * self.data.last_price(pos.ticker) * y * (period_days / 365.0)
        self.cash += total
        return round(total, 4)

    def portfolio(self) -> PortfolioState:
        mv = sum(p.quantity * self.data.last_price(p.ticker) for p in self.positions.values())
        return PortfolioState(cash=round(self.cash, 2),
                              positions=list(self.positions.values()),
                              equity=round(self.cash + mv, 2))


class FakeMacro(MacroProvider):
    """Benign macro climate: normal curve, cool inflation, stable jobs, Fed easing."""

    SERIES = {
        "T10Y2Y": [0.4, 0.45, 0.5, 0.52, 0.55],
        "CPIAUCSL": [310 + i * 0.6 for i in range(13)],   # ~2.4% YoY
        "UNRATE": [4.1, 4.1, 4.0, 4.0],
        "FEDFUNDS": [4.5, 4.4, 4.3, 4.2, 4.1, 4.0, 3.9],
    }

    def get_series(self, series_id: str, limit: int = 24) -> list[float]:
        return self.SERIES.get(series_id, [])[-limit:]
