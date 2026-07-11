"""Add cash to the paper portfolio AND the shadow benchmark — always both,
so the scoreboard stays fair. Usage: python scripts/deposit.py 100"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_investor.orchestrator.registry import Registry

ROOT = Path(__file__).parent.parent


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/deposit.py AMOUNT")
        return
    amount = float(sys.argv[1])
    reg = Registry(ROOT / "config" / "settings.yaml")
    if not hasattr(reg.broker, "deposit"):
        print("Current broker plugin doesn't support deposits.")
        return
    reg.broker.deposit(amount)
    reg.benchmark.deposit(amount)
    pf = reg.broker.portfolio()
    print(f"Deposited ${amount:.2f} into both portfolio and benchmark.")
    print(f"Portfolio: cash=${pf.cash:.2f} equity=${pf.equity:.2f} | "
          f"Benchmark: ${reg.benchmark.value():.2f}")


if __name__ == "__main__":
    main()
