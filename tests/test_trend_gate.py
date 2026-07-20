from ai_investor.core.models import Bar
from ai_investor.screener.screener import passes_trend_template
from datetime import datetime, timedelta, timezone


def bars_from(closes):
    start = datetime.now(timezone.utc) - timedelta(days=len(closes))
    return [Bar(ticker="X", date=start + timedelta(days=i), open=c, high=c,
                low=c, close=c, volume=1_000_000)
            for i, c in enumerate(closes)]


def test_steady_uptrend_passes():
    closes = [100 * (1.002 ** i) for i in range(260)]
    assert passes_trend_template(bars_from(closes))


def test_downtrend_fails():
    closes = [200 * (0.998 ** i) for i in range(260)]
    assert not passes_trend_template(bars_from(closes))


def test_crashed_off_high_fails():
    closes = [100 * (1.003 ** i) for i in range(230)] + [60] * 30
    assert not passes_trend_template(bars_from(closes))


def test_short_history_fails():
    assert not passes_trend_template(bars_from([100] * 50))
