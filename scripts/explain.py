"""Usage:
  python scripts/explain.py              -> recent runs
  python scripts/explain.py NVDA         -> recent NVDA runs
  python scripts/explain.py --id RUN_ID  -> full reasoning chain for one run"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_investor.audit.store import AuditStore

store = AuditStore(Path(__file__).parent.parent / "runs" / "audit.db")

if len(sys.argv) > 2 and sys.argv[1] == "--id":
    print(store.explain(sys.argv[2]) or "run not found")
else:
    ticker = sys.argv[1] if len(sys.argv) > 1 else None
    for r in store.history(ticker):
        print(f"{r['started_at'][:19]}  {r['ticker']:5} {r['signal'] or '-':4} "
              f"conf={r['confidence'] or 0:.2f} {r['verdict'] or '-':7} "
              f"{'filled@' + format(r['fill_price'], '.2f') if r['filled'] else 'no-fill':>14} "
              f" id={r['run_id']}")
