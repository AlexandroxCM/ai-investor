from unittest.mock import MagicMock, patch

from ai_investor.agents.macro import MacroAgent
from ai_investor.plugins.fakes import FakeMacro


def test_benign_macro_scores_positive():
    agent = MacroAgent(FakeMacro())
    rep = agent.run_market()
    assert rep.score > 0
    assert rep.confidence > 0
    assert any("yield curve normal" in e for e in rep.evidence)
    assert any("Fed easing" in e for e in rep.evidence)


def test_inverted_curve_and_hot_inflation_score_negative():
    class BadMacro(FakeMacro):
        SERIES = {
            "T10Y2Y": [-0.2, -0.3, -0.5],
            "CPIAUCSL": [300 * (1.05 ** (i / 12)) for i in range(13)],  # ~5% YoY
            "UNRATE": [3.8, 4.0, 4.2, 4.4],
            "FEDFUNDS": [4.0] * 7,
        }
    rep = MacroAgent(BadMacro()).run_market()
    assert rep.score < 0
    assert any("inverted" in e for e in rep.evidence)
    assert any("inflation hot" in e for e in rep.evidence)
    assert any("unemployment rising" in e for e in rep.evidence)


def test_macro_report_is_cached():
    macro = FakeMacro()
    macro.get_series = MagicMock(side_effect=macro.get_series)
    agent = MacroAgent(macro)
    agent.run_market()
    calls_after_first = macro.get_series.call_count
    agent.run_market()
    assert macro.get_series.call_count == calls_after_first


def test_fred_plugin_parses_and_skips_missing(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test")
    from ai_investor.plugins.macro import fred as fred_mod
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"observations": [
        {"value": "4.1"}, {"value": "."}, {"value": "4.0"}]}  # desc order
    fake_resp.raise_for_status = MagicMock()
    with patch.object(fred_mod.requests, "get", return_value=fake_resp):
        vals = fred_mod.FredMacro().get_series("UNRATE", limit=3)
    assert vals == [4.0, 4.1]  # reversed to oldest-first, '.' dropped
