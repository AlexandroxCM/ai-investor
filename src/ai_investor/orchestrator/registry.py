"""Reads settings.yaml and wires concrete plugins. Adding a real provider =
add a class + one entry here. Nothing else in the codebase changes."""
from __future__ import annotations

from pathlib import Path

import yaml

from ai_investor.core.benchmark import ShadowBenchmark
from ai_investor.plugins.fakes import (FakeBroker, FakeLLM, FakeMacro,
                                       FakeMarketData, FakeNews)
from ai_investor.plugins.notifiers import ConsoleNotifier, DiscordNotifier


class Registry:
    def __init__(self, settings_path: str | Path):
        self.settings = yaml.safe_load(Path(settings_path).read_text())
        p = self.settings["plugins"]

        self.llm = self._make_llm(p["llm"])
        self.market_data = self._make_market_data(p["market_data"])
        self.news = self._make_news(p["news"])
        self.macro = self._make_macro(p.get("macro", "fake"))

        broker_impls = {
            "fake": lambda: FakeBroker(self.market_data,
                                       self.settings["run"]["starting_cash"],
                                       self.settings["run"].get("slippage_bps", 5)),
        }
        self.broker = broker_impls[p["broker"]]()

        notifier_impls = {"console": ConsoleNotifier, "discord": DiscordNotifier}
        self.notifier = notifier_impls[p.get("notifier", "console")]()

        self.benchmark = ShadowBenchmark(
            self.market_data, self.settings.get("benchmark", {}).get("ticker", "VOO"))
        self.benchmark.deposit(self.settings["run"]["starting_cash"])

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
            from ai_investor.plugins.news.composite import CompositeNews
            from ai_investor.plugins.news.edgar import EdgarFilings
            from ai_investor.plugins.news.rss import RSSNews
            return CompositeNews([
                EdgarFilings(news_cfg.get("edgar_user_agent", "")),
                RSSNews(news_cfg.get("feeds")),
            ])
        raise ValueError(f"unknown news plugin: {name}")
