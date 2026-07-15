from ai_investor.agents.fundamental import FundamentalAgent
from ai_investor.agents.technical import TechnicalAgent, ema, rsi
from ai_investor.plugins.fakes import FakeFundamentals, FakeMarketData


class Metrics(FakeFundamentals):
    def __init__(self, **overrides):
        self.metrics = dict(self.METRICS)
        self.metrics.update(overrides)

    def get_metrics(self, ticker):
        return dict(self.metrics)


def test_healthy_company_scores_positive():
    agent = FundamentalAgent(FakeFundamentals(), FakeMarketData())
    rep = agent.run("NVDA")
    assert rep.score > 0.3
    assert rep.confidence > 0.5
    assert any("revenue growing" in e for e in [rep.summary])


def test_shrinking_unprofitable_company_scores_negative():
    bad = Metrics(revenue_growth=-0.10, profit_margin=-0.05,
                  free_cash_flow=-1e9, forward_pe=60.0, debt_to_equity=3.0)
    rep = FundamentalAgent(bad, FakeMarketData()).run("XYZ")
    assert rep.score < -0.5
    assert "SHRINKING" in rep.summary


def test_etf_abstains():
    rep = FundamentalAgent(FakeFundamentals(), FakeMarketData()).run("VOO")
    assert rep.score == 0.0
    assert rep.confidence == 0.0
    assert "ETF" in rep.summary


def test_sparse_data_abstains():
    rep = FundamentalAgent(Metrics().__class__(forward_pe=20.0),
                           FakeMarketData()).run("XYZ") if False else None
    sparse = Metrics()
    sparse.metrics = {"forward_pe": 20.0}
    rep = FundamentalAgent(sparse, FakeMarketData()).run("XYZ")
    assert rep.confidence == 0.0


def test_rsi_extremes():
    rising = [100 + i for i in range(30)]
    falling = [130 - i for i in range(30)]
    assert rsi(rising) > 70
    assert rsi(falling) < 30


def test_ema_tracks_direction():
    rising = [100 + i for i in range(30)]
    assert ema(rising, 12)[-1] > ema(rising, 26)[-1]


def test_technical_agent_full_suite_runs():
    rep = TechnicalAgent(FakeMarketData()).run("NVDA")
    assert -1 <= rep.score <= 1
    assert "RSI" in rep.summary
    assert "MACD" in rep.summary
    assert rep.confidence == 0.7


def test_technical_deterministic():
    a = TechnicalAgent(FakeMarketData()).run("AAPL")
    b = TechnicalAgent(FakeMarketData()).run("AAPL")
    assert a.score == b.score
