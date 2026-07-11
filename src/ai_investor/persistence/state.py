"""Persistent portfolio state. Cash, positions, and benchmark holdings live
in runs/state.db so every cycle continues from where the last one ended —
the difference between a demo and a track record."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ai_investor.core.models import Position

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
    ticker   TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL
);
"""


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, key: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str | float) -> None:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, str(value)))

    def load_positions(self) -> dict[str, Position]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM positions").fetchall()
        return {r["ticker"]: Position(ticker=r["ticker"], quantity=r["quantity"],
                                      avg_cost=r["avg_cost"]) for r in rows}

    def save_positions(self, positions: dict[str, Position]) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM positions")
            c.executemany("INSERT INTO positions VALUES (?, ?, ?)",
                          [(p.ticker, p.quantity, p.avg_cost)
                           for p in positions.values()])
