"""Earnings radar: detects which universe companies ACTUALLY filed an 8-K
today (SEC daily index — official, free), so fresh reporters get analyzed
even if momentum rank wouldn't pick them. Post-earnings drift is a patience
trade: we read the filing after close and act at next open, no speed race."""
from __future__ import annotations

from datetime import date, datetime, timezone

import requests

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
DAILY_INDEX_URL = ("https://www.sec.gov/Archives/edgar/daily-index/"
                   "{year}/QTR{quarter}/form.{ymd}.idx")


class EarningsRadar:
    def __init__(self, user_agent: str):
        if not user_agent or "@" not in user_agent:
            raise RuntimeError("EarningsRadar needs the same SEC user agent "
                               "(name + email) as the EDGAR news plugin")
        self.headers = {"User-Agent": user_agent}
        self._cik_to_ticker: dict[int, str] | None = None

    def _cik_map(self) -> dict[int, str]:
        if self._cik_to_ticker is None:
            resp = requests.get(TICKER_MAP_URL, headers=self.headers, timeout=20)
            resp.raise_for_status()
            self._cik_to_ticker = {
                int(row["cik_str"]): row["ticker"]
                for row in resp.json().values()}
        return self._cik_to_ticker

    def _daily_8k_ciks(self, day: date) -> set[int]:
        quarter = (day.month - 1) // 3 + 1
        url = DAILY_INDEX_URL.format(year=day.year, quarter=quarter,
                                     ymd=day.strftime("%Y%m%d"))
        resp = requests.get(url, headers=self.headers, timeout=20)
        if resp.status_code == 403 or resp.status_code == 404:
            return set()  # weekend/holiday: no index published
        resp.raise_for_status()
        ciks: set[int] = set()
        for line in resp.text.splitlines():
            if line.startswith("8-K "):  # exactly 8-K, not 8-K/A etc. is fine too
                parts = line.split()
                # form.idx columns: Form Type, Company Name..., CIK, Date, File.
                # Date may be YYYYMMDD (all digits) or YYYY-MM-DD; the CIK is the
                # second-to-last pure-digit token when both are digits, else the last.
                digits = [t for t in parts if t.isdigit()]
                if len(digits) >= 2:
                    ciks.add(int(digits[-2]))
                elif digits:
                    ciks.add(int(digits[-1]))
        return ciks

    def todays_reporters(self, universe: list[str],
                         day: date | None = None) -> list[str]:
        """Universe tickers that filed an 8-K today (or the given day)."""
        day = day or datetime.now(timezone.utc).date()
        try:
            ciks = self._daily_8k_ciks(day)
            if not ciks:
                return []
            cik_map = self._cik_map()
            filers = {cik_map[c] for c in ciks if c in cik_map}
            return [t for t in universe if t in filers]
        except Exception as e:  # radar failure must never block the cycle
            print(f"[earnings-radar] unavailable: {e}")
            return []
