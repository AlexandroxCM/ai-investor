"""Reads settings.yaml and wires concrete plugins. Adding a real provider =
add a class + one entry here. Nothing else in the codebase changes."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai_investor.core.benchmark import PersistentBenchmark, ShadowBenchmark
from ai_investor.core.env import load_env
from ai_investor.plugins.fakes import (FakeBroker, FakeLLM, FakeMacro,
                                       FakeMarketData, FakeNews)
from ai_investor.plugins.notifiers import ConsoleNotifier, DiscordNotifier


class Registry:
    def __init__(self, settings_path: str | Path):
        settings_path = Path(settings_path).resolve()
        load_env(settings_path.parent.parent)  # .env lives at project root
        self.settings = yaml.safe_load(settings_path.read_text())
        p = self.settings["plugins"]

        self.llm = self._make_llm(p["llm"])
        skeptic_choice = p.get("skeptic_llm") or p["llm"]
        try:
            self.skeptic_llm = (self.llm if skeptic_choice == p["llm"]
                                else self._make_llm(skeptic_choice))
        except RuntimeError as e:  # e.g. GEMINI_API_KEY not set yet
            print(f"[registry] skeptic model unavailable ({e}); using main LLM")
            self.skeptic_llm = self.llm
        self.market_data = self._make_market_data(p["market_data"])
        self.news = self._make_news(p["news"])
        self.macro = self._make_macro(p.get("macro", "fake"))

        run_cfg = self.settings["run"]
        bench_ticker = self.settings.get("benchmark", {}).get("ticker", "VOO")
        slippage = run_cfg.get("slippage_bps", 5)

        if p["broker"] == "paper":
            from ai_investor.persistence.state import StateStore
            from ai_investor.plugins.broker.paper import PaperBroker
            store = StateStore(Path(run_cfg["audit_dir"]) / "state.db")
            self.broker = PaperBroker(self.market_data, store, slippage)
            self.benchmark = PersistentBenchmark(self.market_data, store, bench_ticker)
            if store.get("seeded") is None:  # first ever run: fund both sides once
                self.broker.deposit(run_cfg["starting_cash"])
                self.benchmark.deposit(run_cfg["starting_cash"])
                store.set("seeded", "1")
        elif p["broker"] == "alpaca_paper":
            from ai_investor.persistence.state import StateStore
            from ai_investor.plugins.broker.alpaca import AlpacaBroker
            self.broker = AlpacaBroker()
            store = StateStore(Path(run_cfg["audit_dir"]) / "state_alpaca.db")
            self.benchmark = PersistentBenchmark(self.market_data, store, bench_ticker)
            if store.get("alpaca_bench_seeded") is None:
                # benchmark mirrors whatever Alpaca's paper account starts with
                self.benchmark.deposit(self.broker.portfolio().equity)
                store.set("alpaca_bench_seeded", "1")
        elif p["broker"] == "fake":
            self.broker = FakeBroker(self.market_data, run_cfg["starting_cash"], slippage)
            self.benchmark = ShadowBenchmark(self.market_data, bench_ticker)
            self.benchmark.deposit(run_cfg["starting_cash"])
        else:
            raise ValueError(f"unknown broker plugin: {p['broker']}")

        notifier_impls = {"console": ConsoleNotifier, "discord": DiscordNotifier}
        self.notifier = notifier_impls[p.get("notifier", "console")]()

    def _make_llm(self, name: str):
        if name == "fake":
            return FakeLLM()
        if name in ("groq", "gemini"):
            from ai_investor.plugins.llm.providers import OpenAICompatLLM
            return OpenAICompatLLM(preset=name)
        if name == "ollama":
            from ai_investor.plugins.llm.providers import OllamaLLM
            return OllamaLLM(model=self.settings.get("llm", {}).get("ollama_model",
                                                                    "qwen2.5:14b"))
        raise ValueError(f"unknown llm plugin: {name}")

    def _make_macro(self, name: str):
        if name == "fake":
            return FakeMacro()
        if name == "fred":
            from ai_investor.plugins.macro.fred import FredMacro
            return FredMacro()
        raise ValueError(f"unknown macro plugin: {name}")

    def _make_market_data(self, name: str):
        if name == "fake":
            return FakeMarketData()
        if name == "yfinance":
            from ai_investor.plugins.market_data.yfinance_ import YFinanceData
            return YFinanceData()
        raise ValueError(f"unknown market_data plugin: {name}")

    def _make_news(self, name: str):
        if name == "fake":
            return FakeNews()
        news_cfg = self.settings.get("news", {})
        if name == "rss":
            from ai_investor.plugins.news.rss import RSSNews
            return RSSNews(news_cfg.get("feeds"))
        if name == "edgar":
            from ai_investor.plugins.news.edgar import EdgarFilings
            return EdgarFilings(news_cfg.get("edgar_user_agent", ""))
        if name == "composite":
            import os
            from ai_investor.plugins.news.composite import CompositeNews
            from ai_investor.plugins.news.edgar import EdgarFilings
            from ai_investor.plugins.news.rss import RSSNews
            providers = [EdgarFilings(news_cfg.get("edgar_user_agent", "")),
                         RSSNews(news_cfg.get("feeds"))]
            if os.environ.get("ALPACA_API_KEY"):  # newswire upgrades in automatically
                from ai_investor.plugins.news.alpaca_news import AlpacaNews
                providers.insert(1, AlpacaNews())
            return CompositeNews(providers)
        raise ValueError(f"unknown news plugin: {name}")
