"""Scan universe: S&P 100 constituents + the most-traded ETFs — the liquid,
widely-held names. Static list (constituents change a few times a year);
swap in a fuller S&P 500 list later by editing this file or settings.yaml."""

SP100 = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AIG", "AMD", "AMGN", "AMT", "AMZN",
    "AVGO", "AXP", "BA", "BAC", "BK", "BKNG", "BLK", "BMY", "BRK-B", "C",
    "CAT", "CHTR", "CL", "CMCSA", "COF", "COP", "COST", "CRM", "CSCO", "CVS",
    "CVX", "DE", "DHR", "DIS", "DUK", "EMR", "F", "FDX", "GD", "GE",
    "GILD", "GM", "GOOG", "GOOGL", "GS", "HD", "HON", "IBM", "INTC", "INTU",
    "ISRG", "JNJ", "JPM", "KO", "LIN", "LLY", "LMT", "LOW", "MA", "MCD",
    "MDLZ", "MDT", "MET", "META", "MMM", "MO", "MRK", "MS", "MSFT", "NEE",
    "NFLX", "NKE", "NOW", "NVDA", "ORCL", "PEP", "PFE", "PG", "PLTR", "PM",
    "PYPL", "QCOM", "RTX", "SBUX", "SCHW", "SO", "SPG", "T", "TGT", "TMO",
    "TMUS", "TSLA", "TXN", "UNH", "UNP", "UPS", "USB", "V", "VZ", "WFC",
    "WMT", "XOM",
]

TOP_ETFS = [
    "SPY", "VOO", "QQQ", "IWM", "DIA", "VTI", "XLK", "XLF", "XLE", "XLV",
    "SMH", "SOXX", "ARKK", "GLD", "SLV", "TLT", "HYG", "EEM", "EFA", "VNQ",
]

DEFAULT_UNIVERSE = SP100 + TOP_ETFS


# ---------------------------------------------------------------------------
# Extended universe (~1,500 names). Source order:
#   1. Yahoo market screener (same source as our prices): every US-listed
#      stock above a market-cap and volume floor — wider and more honest
#      than any index committee's list.
#   2. Wikipedia S&P 500/400/600 constituent tables (browser headers).
#   3. The built-in core universe.
# Cached 30 days. Search is cheap; only the screener's top picks reach the LLM.
# ---------------------------------------------------------------------------
import json
import time
from io import StringIO
from pathlib import Path as _Path

CACHE_TTL_DAYS = 30
WIKI_LISTS = {
    "sp500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol"),
    "sp400": ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", "Symbol"),
    "sp600": ("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", "Symbol"),
}
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")


def _yahoo_market_screen(limit: int = 1500,
                         min_market_cap: float = 300_000_000,
                         min_avg_volume: float = 500_000) -> list[str]:
    import yfinance as yf
    query = yf.EquityQuery("and", [
        yf.EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),  # Nasdaq + NYSE
        yf.EquityQuery("gt", ["intradaymarketcap", min_market_cap]),
        yf.EquityQuery("gt", ["avgdailyvol3m", min_avg_volume]),
    ])
    tickers: list[str] = []
    for offset in range(0, limit, 250):
        resp = yf.screen(query, offset=offset, size=250,
                         sortField="intradaymarketcap", sortAsc=False)
        quotes = (resp or {}).get("quotes", [])
        if not quotes:
            break
        tickers.extend(q["symbol"] for q in quotes if q.get("symbol"))
    if len(tickers) < 300:  # a real US market screen returns far more
        raise RuntimeError(f"screen returned only {len(tickers)} symbols")
    return tickers


def _wikipedia_index_lists(include: tuple = ("sp500", "sp400", "sp600")) -> list[str]:
    import pandas as pd
    import requests
    tickers: set[str] = set()
    for key in include:
        url, col = WIKI_LISTS[key]
        html = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=20)
        html.raise_for_status()
        tables = pd.read_html(StringIO(html.text))
        table = next(t for t in tables if col in t.columns)
        tickers.update(str(x).replace(".", "-").strip()
                       for x in table[col].dropna())
    return sorted(tickers)


def load_extended_universe(cache_dir: str | _Path = "runs") -> list[str]:
    cache = _Path(cache_dir) / "universe_cache.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        if time.time() - data.get("fetched_at", 0) < CACHE_TTL_DAYS * 86400:
            return data["tickers"]

    tickers: list[str] | None = None
    try:
        tickers = _yahoo_market_screen()
        source = "yahoo market screen"
    except Exception as e:
        print(f"[universe] yahoo screen unavailable ({e}) — trying index lists")
        try:
            tickers = _wikipedia_index_lists()
            source = "index constituent lists"
        except Exception as e2:
            print(f"[universe] index lists unavailable ({e2}) — using core universe")
            return DEFAULT_UNIVERSE

    out = sorted(set(tickers) | set(TOP_ETFS))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fetched_at": time.time(), "tickers": out,
                                 "source": source}))
    print(f"[universe] extended scan list: {len(out)} symbols via {source} (cached 30d)")
    return out
