from __future__ import annotations

from abc import ABC, abstractmethod

from ai_investor.core.models import AgentReport


class ResearchAgent(ABC):
    """Uniform contract: the orchestrator neither knows nor cares whether
    an agent calls an LLM or runs pure code."""

    name: str

    @abstractmethod
    def run(self, ticker: str) -> AgentReport: ...
