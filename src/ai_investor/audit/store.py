"""SQLite audit trail. Every RunRecord lands here, queryable forever.
'Why did we buy NVDA on July 3?' is one SELECT."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ai_investor.core.models import RunRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    signal      TEXT,
    confidence  REAL,
    verdict     TEXT,
    rules       TEXT,
    filled      INTEGER NOT NULL DEFAULT 0,
    fill_price  REAL,
    record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_ticker ON runs (ticker, started_at);
"""


class AuditStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, rec: RunRecord) -> None:
        p, v, o = rec.proposal, rec.verdict, rec.order
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rec.run_id, rec.started_at.isoformat(),
                 p.ticker if p else "", p.signal.value if p else None,
                 p.confidence if p else None,
                 v.action.value if v else None,
                 ",".join(v.rules_triggered) if v else None,
                 1 if (o and o.fill_price) else 0,
                 o.fill_price if o else None,
                 rec.model_dump_json()))

    def history(self, ticker: str | None = None, limit: int = 50) -> list[dict]:
        q = "SELECT run_id, started_at, ticker, signal, confidence, verdict, rules, filled, fill_price FROM runs"
        args: tuple = ()
        if ticker:
            q += " WHERE ticker = ?"
            args = (ticker,)
        q += " ORDER BY started_at DESC LIMIT ?"
        with self._conn() as c:
            return [dict(r) for r in c.execute(q, args + (limit,))]

    def explain(self, run_id: str) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT record_json FROM runs WHERE run_id = ?",
                            (run_id,)).fetchone()
        return row["record_json"] if row else None
