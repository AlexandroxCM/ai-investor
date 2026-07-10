"""LLM-backed agent. The provider is injected — fake today, Groq/Ollama later."""
from __future__ import annotations

import json

from ai_investor.agents.base import ResearchAgent
from ai_investor.core.interfaces.providers import LLMProvider, NewsProvider
from ai_investor.core.models import AgentReport

SYSTEM = ("You are a financial news analyst. Weight sources by reliability: "
          "regulatory filings are ground truth, earnings coverage is strong signal, "
          "general news is weak signal. Respond ONLY with JSON: "
          "{\"sentiment\": float -1..1, \"confidence\": float 0..1, \"summary\": str}")

TIER_LABEL = {1: "FILING", 2: "EARNINGS", 3: "NEWS"}


class NewsAgent(ResearchAgent):
    name = "news"

    def __init__(self, llm: LLMProvider, news: NewsProvider):
        self.llm = llm
        self.news = news

    def run(self, ticker: str) -> AgentReport:
        articles = self.news.get_articles(ticker)
        if not articles:
            return AgentReport(agent=self.name, ticker=ticker, score=0.0,
                               confidence=0.0, summary="no recent news")
        digest = "\n".join(
            f"- [{TIER_LABEL.get(a.tier, 'NEWS')}] {a.headline}: {a.body[:200]}"
            for a in articles)
        raw = self.llm.complete(f"Ticker {ticker}. Recent news:\n{digest}", system=SYSTEM)
        try:
            parsed = json.loads(raw)
            return AgentReport(
                agent=self.name, ticker=ticker,
                score=float(parsed["sentiment"]),
                confidence=float(parsed["confidence"]),
                summary=str(parsed["summary"]),
                evidence=[f"[{TIER_LABEL.get(a.tier, 'NEWS')}] {a.headline}" for a in articles],
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Malformed LLM output must never flow downstream.
            return AgentReport(agent=self.name, ticker=ticker, score=0.0,
                               confidence=0.0, summary="LLM response unparseable — neutral")
