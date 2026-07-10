"""Shadow benchmark: every dollar the system receives, a phantom portfolio
puts into an index ETF at the same moment. The scoreboard is automatic and
unarguable — the weekly report always answers 'are we beating boring?'"""
from __future__ import annotations

from ai_investor.core.interfaces.providers import MarketDataProvider


class ShadowBenchmark:
    def __init__(self, data: MarketDataProvider, ticker: str = "VOO"):
        self.data = data
        self.ticker = ticker
        self.shares = 0.0
        self.cash = 0.0
        self.deposited = 0.0

    def deposit(self, amount: float) -> None:
        """Buy the benchmark immediately with the full deposit."""
        price = self.data.last_price(self.ticker)
        self.shares += amount / price
        self.deposited += amount

    def apply_dividends(self, period_days: int) -> float:
        """Credit dividends accrued over period_days, reinvested."""
        price = self.data.last_price(self.ticker)
        y = self.data.dividend_yield(self.ticker)
        paid = self.shares * price * y * (period_days / 365.0)
        self.shares += paid / price
        return round(paid, 4)

    def value(self) -> float:
        return round(self.shares * self.data.last_price(self.ticker) + self.cash, 2)

    def return_pct(self) -> float:
        if self.deposited == 0:
            return 0.0
        return round((self.value() / self.deposited - 1) * 100, 2)
