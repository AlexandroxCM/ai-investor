"""Pre-market research pass. Run manually or via autostart at 6:15am PT.
Usage: python scripts/morning_briefing.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_investor.agents.macro import MacroAgent
from ai_investor.agents.market_research import MarketResearchAgent
from ai_investor.orchestrator.registry import Registry
from ai_investor.screener.universe import DEFAULT_UNIVERSE

ROOT = Path(__file__).parent.parent


def main() -> None:
    reg = Registry(ROOT / "config" / "settings.yaml")
    macro = MacroAgent(reg.macro).run_market()
    agent = MarketResearchAgent(reg.market_data, reg.llm, DEFAULT_UNIVERSE)
    briefing = agent.briefing(macro_summary=macro.summary)
    path = agent.save(briefing, ROOT / reg.settings["run"]["audit_dir"])
    msg = (f"Morning briefing [{briefing['metrics']['regime'].upper()}]: "
           f"{briefing['briefing']}")
    print(msg)
    print(f"saved: {path}")
    reg.notifier.send(msg)


if __name__ == "__main__":
    main()
