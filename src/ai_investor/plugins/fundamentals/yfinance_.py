"""Real fundamentals via yfinance's info endpoint. Unlike prompting an LLM
to 'search Yahoo and make a table', these numbers come from the API —
they can be missing, but they can't be hallucinated."""
from __future__ import annotations

from ai_investor.core.interfaces.providers import FundamentalsProvider

FIELDS = {
    "forward_pe": "forwardPE",
    "price_to_sales": "priceToSalesTrailing12Months",
    "revenue_growth": "revenueGrowth",
    "profit_margin": "profitMargins",
    "gross_margin": "grossMargins",
    "debt_to_equity": "debtToEquity",   # yfinance reports this in percent
    "free_cash_flow": "freeCashflow",
}


class YFinanceFundamentals(FundamentalsProvider):
    def __init__(self):
        import yfinance
        self._yf = yfinance
        self._cache: dict[str, dict] = {}

    def get_metrics(self, ticker: str) -> dict:
        if ticker not in self._cache:
            try:
                info = self._yf.Ticker(ticker).info or {}
            except Exception:
                info = {}
            out = {}
            for key, src in FIELDS.items():
                value = info.get(src)
                if value is None:
                    continue
                if key == "debt_to_equity":
                    value = float(value) / 100.0
                out[key] = float(value)
            self._cache[ticker] = out
        return self._cache[ticker]
