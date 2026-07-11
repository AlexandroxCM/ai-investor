"""Plugin contracts. Agents depend on these ABCs, never on concrete plugins."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Article, Bar, Order, PortfolioState


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Return raw model text. Structured parsing happens in the agent."""


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, ticker: str, lookback_days: int) -> list[Bar]: ...

    @abstractmethod
    def last_price(self, ticker: str) -> float: ...

    @abstractmethod
    def dividend_yield(self, ticker: str) -> float:
        """Trailing annual dividend yield as a fraction (0.013 = 1.3%)."""

    def sector(self, ticker: str) -> str:
        """GICS-style sector; 'ETF' for funds; 'Unknown' if undetermined."""
        from ai_investor.screener.sectors import SECTORS
        return SECTORS.get(ticker, "Unknown")


class MacroProvider(ABC):
    @abstractmethod
    def get_series(self, series_id: str, limit: int = 24) -> list[float]:
        """Monthly/daily observations, oldest -> newest, missing values dropped."""


class NewsProvider(ABC):
    @abstractmethod
    def get_articles(self, ticker: str, limit: int = 5) -> list[Article]: ...


class Broker(ABC):
    @abstractmethod
    def submit(self, order: Order) -> Order: ...

    @abstractmethod
    def portfolio(self) -> PortfolioState: ...


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...
