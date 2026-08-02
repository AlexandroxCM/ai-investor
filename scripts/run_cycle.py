"""Run one full pipeline cycle. Universe comes from the watchlist or,
in screener mode, from scanning S&P 100 + top ETFs for the best candidates.
Per-trade budget: fixed dollar amount via run.trade_budget in settings.yaml
(e.g. 100), else defaults to 10% of equity.
Usage: python scripts/run_cycle.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_investor.orchestrator.pipeline import Pipeline
from ai_investor.orchestrator.registry import Registry

ROOT = Path(__file__).parent.parent


def wait_for_network(timeout_s: int = 600) -> bool:
    """Post-wake, wifi can lag the scheduler by a minute. Wait politely."""
    import socket
    import time
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            socket.getaddrinfo("paper-api.alpaca.markets", 443)
            return True
        except OSError:
            print("[net] no network yet, retrying in 10s...")
            time.sleep(10)
    return False



def pick_universe(reg: Registry) -> tuple[list[str], set[str]]:
    """Returns (tickers, earnings_tagged) — reporters ride the earnings strategy."""
    cfg = reg.settings["universe"]
    if cfg.get("mode", "watchlist") != "screener":
        return cfg["watchlist"], set()
    from ai_investor.screener.screener import Screener
    from ai_investor.screener.universe import (DEFAULT_UNIVERSE,
                                               load_extended_universe)
    sc = cfg.get("screener", {})
    if sc.get("scan", "core") == "extended":
        universe = load_extended_universe(reg.settings["run"]["audit_dir"])
    else:
        universe = DEFAULT_UNIVERSE
    held = [p.ticker for p in reg.broker.portfolio().positions]

    reporters: list[str] = []
    ua = reg.settings.get("news", {}).get("edgar_user_agent", "")
    if "@" in ua:
        from ai_investor.screener.earnings import EarningsRadar
        reporters = EarningsRadar(ua).todays_reporters(universe)
        if reporters:
            print(f"Earnings radar: fresh 8-K filers today: {', '.join(reporters)}")

    screener = Screener(reg.market_data, universe,
                        top_n=sc.get("top_n", 12),
                        min_price=sc.get("min_price", 5.0),
                        min_dollar_volume=sc.get("min_dollar_volume", 5_000_000),
                        trend_gate=True)
    print(f"Screening {len(universe)} symbols for top {sc.get('top_n', 12)}...")
    # held names are evaluated for exits separately, NOT force-injected as
    # buy candidates (that caused the same winners to be re-bought daily).
    picks = screener.top_candidates(always_include=reporters)
    # append held names at the end so they still get a sell/hold evaluation
    picks = picks + [t for t in held if t not in picks]
    print(f"Candidates: {', '.join(picks)}")
    return picks, set(reporters)


def main() -> None:
    if not wait_for_network():
        print("[net] no network after 3 minutes — skipping this run")
        return
    reg = Registry(ROOT / "config" / "settings.yaml")
    pipe = Pipeline(reg, ROOT / "config" / "risk_rules.yaml")

    exits = pipe.exit_sweep()
    for rec in exits:
        o = rec.order
        print(f"[{rec.proposal.ticker:5}] EXIT  {rec.verdict.note} "
              f"{'filled @' + format(o.fill_price, '.2f') if o and o.fill_price else '(queued)'}")

    tickers, earnings_set = pick_universe(reg)
    equity = reg.broker.portfolio().equity
    configured = reg.settings["run"].get("trade_budget")
    budget_per_ticker = (float(configured) if configured
                         else max(equity * 0.10, 1.0))
    print(f"Per-trade budget: ${budget_per_ticker:,.2f}"
          + (" (fixed)" if configured else " (10% of equity)"))

    trades = []
    for ticker in tickers:
        rec = pipe.run_cycle(ticker, budget=budget_per_ticker,
                             strategy="earnings" if ticker in earnings_set
                             else "momentum")
        v, o = rec.verdict, rec.order
        tag = " *earnings*" if ticker in earnings_set else ""
        print(f"[{ticker:5}]{tag} proposal={rec.proposal.signal.value:4} "
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
