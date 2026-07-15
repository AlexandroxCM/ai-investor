"""Scan universe: S&P 100 constituents + the most-traded ETFs — the liquid,
widely-held names. Static list (constituents change a few times a year);
swap in a fuller S&P 500 list later by editing this file or settings.yaml."""

SP100 = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AIG", "AMD", "AMGN", "AMT", "AMZN",
    "AVGO", "AXP", "BA", "BAC", "BKNG", "BLK", "BMY", "BRK-B", "C",
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
