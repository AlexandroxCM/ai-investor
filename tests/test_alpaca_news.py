from unittest.mock import MagicMock, patch

from ai_investor.core.enums import Signal
from ai_investor.core.models import Order


def test_alpaca_news_maps_articles(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    from ai_investor.plugins.news import alpaca_news as mod
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"news": [
        {"headline": "NVDA beats on earnings", "summary": "Strong quarter",
         "created_at": "2026-07-10T20:00:00Z", "source": "benzinga"}]}
    with patch.object(mod.requests, "get", return_value=r):
        arts = mod.AlpacaNews().get_articles("NVDA")
    assert len(arts) == 1
    assert arts[0].tier == 2
    assert "benzinga" in arts[0].source


def test_order_carries_client_order_id(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    from ai_investor.plugins.broker import alpaca as mod
    broker = mod.AlpacaBroker(fill_poll_seconds=0, fill_poll_attempts=1)
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = {"id": "o1", "filled_avg_price": "100.0"}
    with patch.object(mod.requests, "post", return_value=r) as post:
        broker.submit(Order(ticker="AAPL", signal=Signal.BUY, quantity=1,
                            client_order_id="NVDA-abc123"))
    assert post.call_args.kwargs["json"]["client_order_id"] == "NVDA-abc123"
