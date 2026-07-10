# ai-investor

Modular multi-agent AI investment platform. **Phase 1: architecture skeleton** — the full pipeline runs end-to-end on deterministic fakes, at $0, with no network calls.

## The pipeline
research agents (technical = pure code, news = LLM) → decision agent → skeptic objections → rebuttals (one round, capped) → risk manager (pure code, unappealable, rules in `config/risk_rules.yaml`) → execution → JSON audit trail in `runs/`

Every plugin (LLM, market data, news, broker) is chosen in `config/settings.yaml`. Swapping fake → Groq/yfinance/Alpaca is a new class + one registry entry.

## Run it
```
pip install -e ".[dev]"
pytest
python scripts/run_cycle.py        # full cycle on current settings
python scripts/explain.py          # audit history; --id RUN_ID for full chain
python scripts/schedule_daily.py   # daily 4:30pm ET cycle + Friday weekly report
python scripts/weekly_report.py    # scoreboard: signals, verdicts, equity vs benchmark
```

## Going live with real data (Phase 2 smoke test)
1. In `config/settings.yaml` set `market_data: yfinance` and `news: composite` (EDGAR 8-K filings + RSS, deduped, filings ranked first — put your real email in `edgar_user_agent`, SEC blocks anonymous requests). Run a cycle; technical + news agents are now real.
2. Get a free key at console.groq.com, `export GROQ_API_KEY=...`, set `llm: groq` — news analysis and theses are now real.
2b. Free key at fred.stlouisfed.org, `export FRED_API_KEY=...`, set `macro: fred` — the macro agent reads real rates/CPI/yield-curve data.
3. Keep `broker: fake` until Phase 5. Real money is earned with receipts, not enthusiasm.

## Built-in honesty features
- **Shadow benchmark**: every deposit phantom-buys VOO; every cycle reports portfolio vs. benchmark. The scoreboard is automatic and unarguable.
- **Slippage**: paper fills take a configurable haircut (`slippage_bps`), always against you. Paper results should be pessimistic, not flattering.
- **Dividends**: benchmark reinvests them, broker credits them — the comparison is fair in both directions.
- **Drawdown kill switch**: persistent high-water mark; past `max_drawdown_halt_pct` ALL trading halts until a human runs `scripts/reset_kill_switch.py`. Halting is automatic; resuming never is.
- **Notifications**: one-liner per cycle via console or Discord webhook (`DISCORD_WEBHOOK_URL`). A system you don't hear from is a system you stop trusting.

## Roadmap
- Phase 1 ✅ skeleton on fakes, audit trail, tests, benchmark, slippage, dividends, kill switch, notifications
- Phase 2 (built, needs live verification): real plugins — yfinance market data, RSS news, Groq/Gemini/Ollama LLMs — plus SQLite audit trail (`runs/audit.db`, query with `scripts/explain.py`) and daily 4:30pm ET scheduler (`scripts/schedule_daily.py`). Go live by editing `config/settings.yaml` plugin names; network calls are mocked in tests and need one real-world smoke run
- Phase 3: backtest engine (grows out of FakeBroker) + forward paper trading vs. VOO benchmark
- Phase 4: screener (S&P 500 + NDX + top ETFs → ~20 candidates/cycle), FastAPI + React dashboard
- Phase 5+: Alpaca paper, then (maybe, with receipts) live
