from pathlib import Path

from ai_investor.orchestrator.pipeline import Pipeline
from ai_investor.orchestrator.registry import Registry

ROOT = Path(__file__).parent.parent


def test_full_cycle_on_fakes(tmp_path):
    reg = Registry(ROOT / "config" / "settings.yaml")
    reg.settings["run"]["audit_dir"] = str(tmp_path)
    pipe = Pipeline(reg, ROOT / "config" / "risk_rules.yaml")

    rec = pipe.run_cycle("NVDA", budget=200)

    assert len(rec.reports) == 3                      # technical + news + macro ran
    assert {r.agent for r in rec.reports} == {"technical", "news", "macro"}
    assert rec.proposal is not None
    assert rec.verdict is not None
    assert (tmp_path / f"{rec.run_id}.json").exists() # audit trail written


def test_deterministic_market_data():
    reg = Registry(ROOT / "config" / "settings.yaml")
    a = reg.market_data.get_bars("AAPL", 30)
    b = reg.market_data.get_bars("AAPL", 30)
    assert [x.close for x in a] == [x.close for x in b]
