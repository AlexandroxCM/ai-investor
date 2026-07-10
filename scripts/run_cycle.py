"""Run one full pipeline cycle per watchlist ticker, entirely on fakes.
Usage: python scripts/run_cycle.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_investor.orchestrator.pipeline import Pipeline
from ai_investor.orchestrator.registry import Registry

ROOT = Path(__file__).parent.parent


def main() -> None:
    reg = Registry(ROOT / "config" / "settings.yaml")
    pipe = Pipeline(reg, ROOT / "config" / "risk_rules.yaml")
    budget_per_ticker = reg.settings["run"]["starting_cash"] * 0.2

    trades = []
    for ticker in reg.settings["universe"]["watchlist"]:
        rec = pipe.run_cycle(ticker, budget=budget_per_ticker)
        v, o = rec.verdict, rec.order
        print(f"[{ticker:5}] proposal={rec.proposal.signal.value:4} "
              f"conf={rec.proposal.confidence:.2f} verdict={v.action.value:7} "
              f"order={'filled @' + format(o.fill_price, '.2f') if o and o.fill_price else '-':>14} "
              f"audit=runs/{rec.run_id}.json")
        if o and o.fill_price:
            trades.append(f"{o.signal.value} {o.quantity} {ticker}")

    pf = reg.broker.portfolio()
    bench = reg.benchmark
    diff = pf.equity - bench.value()
    print(f"\nPortfolio: cash=${pf.cash:.2f} equity=${pf.equity:.2f}")
    print(f"Benchmark ({bench.ticker}): ${bench.value():.2f} ({bench.return_pct():+.2f}%)")
    print(f"vs benchmark: {'+' if diff >= 0 else ''}{diff:.2f}")

    reg.notifier.send(
        f"Cycle done. Trades: {', '.join(trades) if trades else 'none'}. "
        f"Portfolio ${pf.equity:.2f} vs {bench.ticker} ${bench.value():.2f} "
        f"({'+' if diff >= 0 else ''}{diff:.2f}).")


if __name__ == "__main__":
    main()
