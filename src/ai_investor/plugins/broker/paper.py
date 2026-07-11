"""Persistent paper broker: FakeBroker's fill logic + durable state.
Every submit/deposit/dividend is written through to state.db immediately."""
from __future__ import annotations

from ai_investor.persistence.state import StateStore
from ai_investor.plugins.fakes import FakeBroker


class PaperBroker(FakeBroker):
    def __init__(self, data, store: StateStore, slippage_bps: float = 5.0):
        super().__init__(data, starting_cash=0.0, slippage_bps=slippage_bps)
        self.store = store
        cash = store.get("broker_cash")
        self.cash = float(cash) if cash is not None else 0.0
        self.positions = store.load_positions()

    def _persist(self) -> None:
        self.store.set("broker_cash", round(self.cash, 6))
        self.store.save_positions(self.positions)

    def deposit(self, amount: float) -> None:
        self.cash += amount
        self._persist()

    def submit(self, order):
        result = super().submit(order)
        self._persist()
        return result

    def apply_dividends(self, period_days: int) -> float:
        paid = super().apply_dividends(period_days)
        self._persist()
        return paid
