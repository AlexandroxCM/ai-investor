"""Real market data via yfinance (unofficial Yahoo API — free, breaks
occasionally; that's why it lives behind MarketDataProvider)."""
from __future__ import annotations

from datetime import datetime, timezone

from ai_investor.core.interfaces.providers import MarketDataProvider
from ai_investor.core.models import Bar


class YFinanceData(MarketDataProvider):
    def __init__(self):
        import logging
        import yfinance  # lazy: keeps fakes-only environments dependency-free
        # yfinance shouts about every straggler ticker; our code already
        # skips them gracefully, so mute the megaphone
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        try:  # macOS caps a process at ~256 open files; bulk downloads need more
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            if soft < 4096:
                resource.setrlimit(resource.RLIMIT_NOFILE,
                                   (min(4096, hard if hard > 0 else 4096), hard))
        except Exception:
            pass
        self._yf = yfinance
        self._cache: dict[str, object] = {}

    def _ticker(self, ticker: str):
        if ticker not in self._cache:
            self._cache[ticker] = self._yf.Ticker(ticker)
        return self._cache[ticker]

    def get_bars(self, ticker: str, lookback_days: int) -> list[Bar]:
        hist = self._ticker(ticker).history(period=f"{max(lookback_days, 5)}d",
                                            interval="1d", auto_adjust=True).dropna()
        bars = []
        for idx, row in hist.iterrows():
            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            bars.append(Bar(ticker=ticker, date=ts,
                            open=float(row["Open"]), high=float(row["High"]),
                            low=float(row["Low"]), close=float(row["Close"]),
                            volume=int(row["Volume"])))
        return bars

    def get_bars_bulk(self, tickers: list[str],
                      lookback_days: int) -> dict[str, list]:
        """Batched downloads, chunked so very large universes stay reliable."""
        if len(tickers) > 150:
            import time as _time
            out: dict[str, list] = {}
            for i in range(0, len(tickers), 150):
                try:
                    out.update(self.get_bars_bulk(tickers[i:i + 150], lookback_days))
                except Exception as e:
                    print(f"[market_data] chunk {i}-{i+150} failed, skipping: {e}")
                _time.sleep(1.0)  # let sockets/file handles drain between chunks
            return out
        df = self._yf.download(tickers=" ".join(tickers),
                               period=f"{max(lookback_days, 5)}d", interval="1d",
                               auto_adjust=True, group_by="ticker",
                               progress=False, threads=4)
        out: dict[str, list] = {}
        for t in tickers:
            try:
                sub = df[t].dropna() if len(tickers) > 1 else df.dropna()
            except KeyError:
                continue
            bars = []
            for idx, row in sub.iterrows():
                ts = idx.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                bars.append(Bar(ticker=t, date=ts,
                                open=float(row["Open"]), high=float(row["High"]),
                                low=float(row["Low"]), close=float(row["Close"]),
                                volume=int(row["Volume"])))
            if bars:
                out[t] = bars
        return out

    def last_price(self, ticker: str) -> float:
        bars = self.get_bars(ticker, 5)
        if not bars:
            raise RuntimeError(f"no price data for {ticker}")
        return bars[-1].close

    def sector(self, ticker: str) -> str:
        from ai_investor.screener.sectors import SECTORS
        if ticker in SECTORS:
            return SECTORS[ticker]
        if not hasattr(self, "_sector_cache"):
            self._sector_cache: dict[str, str] = {}
        if ticker not in self._sector_cache:
            try:
                info = self._ticker(ticker).info or {}
                self._sector_cache[ticker] = info.get("sector") or (
                    "ETF" if info.get("quoteType") == "ETF" else "Unknown")
            except Exception:
                self._sector_cache[ticker] = "Unknown"
        return self._sector_cache[ticker]

    def dividend_yield(self, ticker: str) -> float:
        info = self._ticker(ticker).info or {}
        y = info.get("dividendYield") or 0.0
        return float(y) if y < 1 else float(y) / 100.0  # yfinance is inconsistent here
