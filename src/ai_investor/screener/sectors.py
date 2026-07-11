"""Ticker -> sector map for the scan universe. Static on purpose: GICS
sectors change about as often as company names do. Unknown tickers fall
back to a live lookup (yfinance) or 'Unknown'."""

SECTORS = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AVGO": "Technology", "ORCL": "Technology", "CRM": "Technology",
    "ADBE": "Technology", "AMD": "Technology", "INTC": "Technology",
    "QCOM": "Technology", "TXN": "Technology", "IBM": "Technology",
    "NOW": "Technology", "INTU": "Technology", "ACN": "Technology",
    "CSCO": "Technology", "PLTR": "Technology",
    # Communication Services
    "GOOG": "Communication", "GOOGL": "Communication", "META": "Communication",
    "NFLX": "Communication", "DIS": "Communication", "CMCSA": "Communication",
    "T": "Communication", "VZ": "Communication", "TMUS": "Communication",
    "CHTR": "Communication",
    # Consumer Discretionary
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "LOW": "Consumer Discretionary",
    "SBUX": "Consumer Discretionary", "BKNG": "Consumer Discretionary",
    "TGT": "Consumer Discretionary", "F": "Consumer Discretionary",
    "GM": "Consumer Discretionary",
    # Consumer Staples
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "COST": "Consumer Staples", "WMT": "Consumer Staples", "PM": "Consumer Staples",
    "MO": "Consumer Staples", "MDLZ": "Consumer Staples", "CL": "Consumer Staples",
    # Financials
    "BRK-B": "Financials", "JPM": "Financials", "BAC": "Financials",
    "WFC": "Financials", "GS": "Financials", "MS": "Financials",
    "SCHW": "Financials", "AXP": "Financials", "C": "Financials",
    "BLK": "Financials", "COF": "Financials", "USB": "Financials",
    "BK": "Financials", "MET": "Financials", "AIG": "Financials",
    "V": "Financials", "MA": "Financials", "PYPL": "Financials", "SPG": "Financials",
    # Health Care
    "LLY": "Health Care", "UNH": "Health Care", "JNJ": "Health Care",
    "ABBV": "Health Care", "MRK": "Health Care", "TMO": "Health Care",
    "PFE": "Health Care", "ABT": "Health Care", "DHR": "Health Care",
    "AMGN": "Health Care", "ISRG": "Health Care", "MDT": "Health Care",
    "BMY": "Health Care", "GILD": "Health Care", "CVS": "Health Care",
    # Industrials
    "GE": "Industrials", "CAT": "Industrials", "RTX": "Industrials",
    "HON": "Industrials", "UNP": "Industrials", "BA": "Industrials",
    "DE": "Industrials", "LMT": "Industrials", "UPS": "Industrials",
    "GD": "Industrials", "MMM": "Industrials", "FDX": "Industrials",
    "EMR": "Industrials",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    # Utilities / Real Estate / Materials
    "NEE": "Utilities", "SO": "Utilities", "DUK": "Utilities",
    "AMT": "Real Estate", "LIN": "Materials",
    # ETFs get their own bucket: they're already diversified
    "SPY": "ETF", "VOO": "ETF", "QQQ": "ETF", "IWM": "ETF", "DIA": "ETF",
    "VTI": "ETF", "XLK": "ETF", "XLF": "ETF", "XLE": "ETF", "XLV": "ETF",
    "SMH": "ETF", "SOXX": "ETF", "ARKK": "ETF", "GLD": "ETF", "SLV": "ETF",
    "TLT": "ETF", "HYG": "ETF", "EEM": "ETF", "EFA": "ETF", "VNQ": "ETF",
}
