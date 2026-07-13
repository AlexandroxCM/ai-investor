"""Alpaca paper-trading broker. Same Broker interface as the local paper
sim, but orders hit Alpaca's real brokerage infrastructure with their
sandbox money. Live trading later = changing the base URL — nothing else.

Keys: ALPACA_API_KEY / ALPACA_SECRET_KEY in .env (paper keys from the
Alpaca dashboard; no bank account needed for paper)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import requests

from ai_investor.core.enums import OrderStatus, Signal
from ai_investor.core.interfaces.providers import Broker
from ai_investor.core.models import Order, PortfolioState, Position

PAPER_URL = "https://paper-api.alpaca.markets"


class AlpacaBroker(Broker):
    def __init__(self, base_url: str = PAPER_URL,
                 api_key: str | None = None, secret: str | None = None,
                 fill_poll_seconds: float = 2.0, fill_poll_attempts: int = 5):
        self.base_url = base_url
        key = api_key or os.environ.get("ALPACA_API_KEY", "")
        sec = secret or os.environ.get("ALPACA_SECRET_KEY", "")
        if not key or not sec:
            raise RuntimeError("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY in .env "
                               "(paper keys from app.alpaca.markets)")
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}
        self.fill_poll_seconds = fill_poll_seconds
        self.fill_poll_attempts = fill_poll_attempts

    def _get(self, path: str):
        r = requests.get(f"{self.base_url}{path}", headers=self.headers, timeout=20)
        r.raise_for_status()
        return r.json()

    def submit(self, order: Order) -> Order:
        payload = {"symbol": order.ticker,
                   "qty": str(order.quantity),
                   "side": "buy" if order.signal == Signal.BUY else "sell",
                   "type": "market",
                   "time_in_force": "day"}
        if order.client_order_id:
            payload["client_order_id"] = order.client_order_id
        r = requests.post(f"{self.base_url}/v2/orders", headers=self.headers,
                          json=payload, timeout=20)
        if r.status_code == 403:  # insufficient buying power / not allowed
            order.status = OrderStatus.REJECTED
            print(f"[alpaca] order rejected: {r.text[:200]}")
            return order
        r.raise_for_status()
        alpaca_order = r.json()

        # Market orders fill in seconds during trading hours; poll briefly.
        for _ in range(self.fill_poll_attempts):
            if alpaca_order.get("filled_avg_price"):
                break
            time.sleep(self.fill_poll_seconds)
            alpaca_order = self._get(f"/v2/orders/{alpaca_order['id']}")

        if alpaca_order.get("filled_avg_price"):
            order.status = OrderStatus.FILLED
            order.fill_price = float(alpaca_order["filled_avg_price"])
            order.filled_at = datetime.now(timezone.utc)
        else:
            # after hours: order is queued for next open — recorded, not filled yet
            order.status = OrderStatus.SUBMITTED
            print(f"[alpaca] {order.ticker} order accepted, will fill at next open")
        return order

    def portfolio(self) -> PortfolioState:
        account = self._get("/v2/account")
        raw_positions = self._get("/v2/positions")
        positions = [Position(ticker=p["symbol"],
                              quantity=float(p["qty"]),
                              avg_cost=float(p["avg_entry_price"]))
                     for p in raw_positions]
        return PortfolioState(cash=float(account["cash"]),
                              positions=positions,
                              equity=float(account["equity"]))
