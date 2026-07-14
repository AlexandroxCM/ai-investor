# ai-investor

An autonomous multi-agent AI investment platform that researches the market, debates its own ideas, enforces hard risk rules, and trades on real brokerage infrastructure — built to run at **$0/month** on free data and free-tier AI.

**Every trade is explainable. Every decision is traceable. No black box.**

> ⚠️ Personal engineering project, paper trading by design. Nothing here is investment advice. The honest expectation for any retail system on daily bars is that it roughly tracks or trails the index — the built-in benchmark exists to prove or disprove exactly that.

## How it works

Ten specialized agents, one cycle per trading day after close:

```
Screener (122 symbols: S&P 100 + top ETFs, momentum + liquidity — pure code)
   + Earnings Radar (who ACTUALLY filed an 8-K today, via SEC daily index)
        │  top ~12 candidates
        ▼
Research agents ──► Technical (pure code) · News (LLM, tiered sources) · Macro (FRED, pure code)
        ▼
Decision Agent (LLM) — writes a thesis, proposes buy/sell/hold
        ▼
Skeptic Agent (different LLM) — argues against it
        ▼
Rebuttals — Decision must answer every objection
        ▼
Skeptic Verdict — judges each rebuttal SUSTAIN/WITHDRAWN; sustained doubt docks confidence
        ▼
Risk Manager (PURE CODE, unappealable) — position caps, sector caps (40%), cash floor,
   confidence floor, cooldowns, pending-order awareness, drawdown kill switch
        ▼
Execution — idempotent orders (client_order_id = audit run_id) to Alpaca paper
        ▼
Audit trail (SQLite + JSON) — the full reasoning chain behind every trade, forever
```

Deterministic **stop-loss / take-profit exits run before every cycle and no AI can veto them** — safety rails don't debate.

## The honest scoreboard

Every dollar deposited is mirrored into a phantom **VOO benchmark**. The dashboard, daily notification, and weekly report all lead with one number: *edge vs. boring*. Paper fills take a slippage haircut, dividends are credited both sides, and strategies (momentum / earnings-drift / risk exits) are scored separately.

## Stack ($0/month)

Python · Pydantic · FastAPI dashboard · SQLite · yfinance + Alpaca (prices) · SEC EDGAR (filings, earnings radar) · RSS + Alpaca newswire (news, deduped + tier-ranked) · FRED (macro) · Groq / Gemini free tiers (LLM, provider-agnostic plugins) · Alpaca paper (brokerage)

Every external service is a **plugin behind an interface** — swapping providers is a YAML edit. The full pipeline runs end-to-end on deterministic fakes, so tests are free and CI needs no keys.

## Run it

```bash
pip install -e ".[dev]"
pytest                              # 60+ tests, no network needed
python scripts/run_cycle.py         # one full trading cycle
python scripts/dashboard.py         # audit desk at localhost:8017
python scripts/explain.py --id RUN  # full reasoning chain for any trade
python scripts/weekly_report.py     # scoreboard by strategy
python scripts/schedule_daily.py    # daily 4:30pm ET + Friday report
```

Config: plugins in `config/settings.yaml`, every risk limit in `config/risk_rules.yaml`, keys in `.env` (see `.env.example`).

## Battle scars (kept on purpose)

- The risk manager rejected its first-ever real trade (confidence floor) — and later vetoed the system's highest-conviction pick because the cash floor outranked conviction.
- The first Alpaca cycle exposed that queued after-hours orders bypassed sector/cash limits (they weren't positions yet) — fixed with pending-exposure tracking the same night, with a regression test recreating the exact pileup.
- The Skeptic's rebuttals initially just restated the thesis ("consensus theater") — now a second model judges every rebuttal and sustained objections dock confidence.

## Screenshots

*(dashboard: equity vs benchmark, run ledger with verdicts, per-trade reasoning transcript)*

<!-- Add: docs/screenshot-dashboard.png, docs/screenshot-transcript.png -->
