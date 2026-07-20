from unittest.mock import MagicMock, patch

import pytest

from ai_investor.core.enums import OrderStatus, Signal
from ai_investor.core.models import Order


def make_broker(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    from ai_investor.plugins.broker.alpaca import AlpacaBroker
    return AlpacaBroker(fill_poll_seconds=0, fill_poll_attempts=1)


def resp(json_data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


def test_requires_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    from ai_investor.plugins.broker.alpaca import AlpacaBroker
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        AlpacaBroker()


def test_submit_marks_filled_order(monkeypatch):
    broker = make_broker(monkeypatch)
    from ai_investor.plugins.broker import alpaca as mod
    with patch.object(mod.requests, "request",
                      return_value=resp({"id": "o1", "filled_avg_price": "101.50"})):
        order = broker.submit(Order(ticker="AAPL", signal=Signal.BUY, quantity=1))
    assert order.status == OrderStatus.FILLED
    assert order.fill_price == 101.50


def test_submit_after_hours_stays_submitted(monkeypatch):
    broker = make_broker(monkeypatch)
    from ai_investor.plugins.broker import alpaca as mod
    pending = {"id": "o1", "filled_avg_price": None}
    with patch.object(mod.requests, "request", return_value=resp(pending)):
        order = broker.submit(Order(ticker="AAPL", signal=Signal.BUY, quantity=1))
    assert order.status == OrderStatus.SUBMITTED
    assert order.fill_price is None


def test_rejected_on_403(monkeypatch):
    broker = make_broker(monkeypatch)
    from ai_investor.plugins.broker import alpaca as mod
    r = resp({}, status=403)
    r.text = "insufficient buying power"
    with patch.object(mod.requests, "request", return_value=r):
        order = broker.submit(Order(ticker="AAPL", signal=Signal.BUY, quantity=999))
    assert order.status == OrderStatus.REJECTED


def test_portfolio_maps_account_and_positions(monkeypatch):
    broker = make_broker(monkeypatch)
    from ai_investor.plugins.broker import alpaca as mod

    def fake_request(method, url, headers=None, timeout=None, **kw):
        if url.endswith("/v2/account"):
            return resp({"cash": "95000.50", "equity": "100200.25"})
        return resp([{"symbol": "NVDA", "qty": "2.5", "avg_entry_price": "180.00"}])

    with patch.object(mod.requests, "request", side_effect=fake_request):
        pf = broker.portfolio()
    assert pf.cash == 95000.50
    assert pf.equity == 100200.25
    assert pf.positions[0].ticker == "NVDA"
    assert pf.positions[0].quantity == 2.5


def test_broker_retries_connection_drops(monkeypatch):
    import requests as req
    broker = make_broker(monkeypatch)
    from ai_investor.plugins.broker import alpaca as mod
    ok = resp({"cash": "2000.0", "equity": "2000.0"})
    with patch.object(mod.requests, "request",
                      side_effect=[req.exceptions.ConnectionError("dns flap"),
                                   req.exceptions.ConnectionError("dns flap"),
                                   ok]):
        with patch.object(mod.time, "sleep"):
            def fake_positions(url_method, url, **kw):
                return resp([])
            # portfolio makes two calls; feed positions after account
            pass
    # simpler: directly exercise _request
    with patch.object(mod.requests, "request",
                      side_effect=[req.exceptions.ConnectionError("x"), ok]):
        with patch.object(mod.time, "sleep"):
            r = broker._request("GET", "/v2/account")
    assert r.json()["equity"] == "2000.0"


def test_broker_gives_up_after_retries(monkeypatch):
    import pytest
    import requests as req
    broker = make_broker(monkeypatch)
    from ai_investor.plugins.broker import alpaca as mod
    with patch.object(mod.requests, "request",
                      side_effect=req.exceptions.ConnectionError("dead")):
        with patch.object(mod.time, "sleep"):
            with pytest.raises(RuntimeError, match="unreachable"):
                broker._request("GET", "/v2/account", retries=3)
