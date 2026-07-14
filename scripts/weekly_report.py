"""Weekly scoreboard from the audit trail. Run manually or via scheduler
(Fridays 4:45pm ET). Usage: python scripts/weekly_report.py [days]"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_investor.orchestrator.registry import Registry

ROOT = Path(__file__).parent.parent
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def main() -> None:
    db = ROOT / "runs" / "audit.db"
    if not db.exists():
        print("No audit database yet — run some cycles first.")
        return

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runs WHERE started_at >= datetime('now', ?) ORDER BY started_at",
        (f"-{DAYS} days",)).fetchall()
    if not rows:
        print(f"No runs in the last {DAYS} days.")
        return

    by_strategy = Counter(r["strategy"] for r in rows
                          if r["filled"] and "strategy" in r.keys())
    signals = Counter(r["signal"] for r in rows if r["signal"])
    verdicts = Counter(r["verdict"] for r in rows if r["verdict"])
    rules = Counter(rule for r in rows if r["rules"]
                    for rule in r["rules"].split(",") if rule)
    fills = [r for r in rows if r["filled"]]

    first, last = json.loads(rows[0]["record_json"]), json.loads(rows[-1]["record_json"])
    eq_start = (first.get("portfolio_after") or {}).get("equity")
    eq_end = (last.get("portfolio_after") or {}).get("equity")
    bm_start, bm_end = first.get("benchmark_value"), last.get("benchmark_value")

    lines = [f"Weekly report ({DAYS}d): {len(rows)} cycles, {len(fills)} fills."]
    lines.append("Signals: " + ", ".join(f"{k}={v}" for k, v in signals.most_common()))
    if by_strategy:
        lines.append("Fills by strategy: "
                     + ", ".join(f"{k}={v}" for k, v in by_strategy.most_common()))
    lines.append("Verdicts: " + ", ".join(f"{k}={v}" for k, v in verdicts.most_common()))
    if rules:
        lines.append("Risk rules triggered: "
                     + ", ".join(f"{k}x{v}" for k, v in rules.most_common()))
    if eq_start and eq_end:
        pnl = eq_end - eq_start
        lines.append(f"Equity: ${eq_start:.2f} -> ${eq_end:.2f} ({pnl:+.2f})")
    if bm_start and bm_end and eq_start and eq_end:
        edge = (eq_end - eq_start) - (bm_end - bm_start)
        lines.append(f"Benchmark: ${bm_start:.2f} -> ${bm_end:.2f}. "
                     f"Edge vs boring: {edge:+.2f}")

    report = "\n".join(lines)

    # Learning Agent: reads the week, writes observations + candidate
    # improvements. Report-only by design — it never rewrites the strategy.
    reg = Registry(ROOT / "config" / "settings.yaml")
    try:
        review = reg.llm.complete(
            "You are the Learning Agent of an automated investment system. "
            "Given this week's stats, write: (1) two observations about the "
            "system's behavior, (2) two candidate improvements for a human to "
            "review. Be specific and skeptical; small samples prove nothing. "
            "Max 90 words total.\n\n" + report)
        report += "\n\n--- Learning Agent review ---\n" + review.strip()
    except Exception as e:
        report += f"\n(learning review unavailable: {type(e).__name__})"

    print(report)
    reg.notifier.send(report)


if __name__ == "__main__":
    main()
