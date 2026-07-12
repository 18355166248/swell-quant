from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from swell_quant.api.server import create_app
from swell_quant.marketdata.records import BarRecord, IndexBarRecord, UniverseMemberRecord
from swell_quant.marketdata.store import MarketStore


def _bar(symbol, day, close):
    return BarRecord(
        symbol=symbol,
        date=date(2026, 1, 1) + timedelta(days=day - 1),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        amount=close * 100,
        adj_factor=1.0,
        source="test",
    )


@pytest.fixture
def client():
    store = MarketStore(":memory:")
    # 三只票几何增长，10 天；日历、指数、成分股快照都备好。
    rates = {"a": 0.0, "b": 0.01, "c": 0.02}
    for sym, rate in rates.items():
        store.write_bars([_bar(sym, d, 10.0 * (1 + rate) ** d) for d in range(1, 11)])
    days = [date(2026, 1, 1) + timedelta(days=d - 1) for d in range(1, 11)]
    store.write_trade_calendar(days)
    store.write_index_bars(
        [IndexBarRecord("sh000300", day, 100.0 + i, "t") for i, day in enumerate(days)]
    )
    store.write_universe_members(
        [UniverseMemberRecord(days[0], "000300", s, date(2010, 1, 1), "t") for s in rates]
    )
    yield TestClient(create_app(store))
    store.close()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta(client):
    data = client.get("/api/meta").json()
    assert data["bars"]["symbols"] == 3
    assert data["bars"]["rows"] == 30
    assert data["universes"][0]["index_code"] == "000300"


def test_factors_catalog(client):
    catalog = client.get("/api/factors").json()["catalog"]
    names = {f["name"] for f in catalog}
    assert {"momentum", "reversal", "value", "quality", "volatility"} <= names


def test_universe(client):
    data = client.get("/api/universe", params={"index": "000300", "as_of": "2026-01-05"}).json()
    assert data["count"] == 3
    assert set(data["symbols"]) == {"a", "b", "c"}


def test_universe_excludes_not_yet_included(client):
    # 成分纳入日 2010；查 2005 应为空（尚未纳入）。
    data = client.get("/api/universe", params={"index": "000300", "as_of": "2005-01-01"}).json()
    assert data["count"] == 0


def test_backtest_runs_and_returns_curve(client):
    body = {
        "factors": [{"name": "momentum", "lookback": 2, "weight": 1.0}],
        "start": "2026-01-01",
        "end": "2026-01-08",
        "step": 2,
        "horizon": 2,
        "top_n": 1,
        "cost_bps": 10,
        "benchmark": "equal_weight",
        "universe_index": "000300",
    }
    data = client.post("/api/backtest", json=body).json()
    assert data["periods"] >= 1
    assert "total_return" in data["metrics"]
    assert len(data["equity_curve"]) == len([p for p in data["equity_curve"]])
    # 每个净值点有 date 和 equity
    assert set(data["equity_curve"][0]) == {"date", "equity"}


def test_backtest_unknown_factor_400(client):
    body = {
        "factors": [{"name": "bogus"}],
        "start": "2026-01-01",
        "end": "2026-01-08",
    }
    assert client.post("/api/backtest", json=body).status_code == 400


def test_factor_ic(client):
    data = client.get(
        "/api/factor-ic",
        params={
            "name": "momentum",
            "lookback": 2,
            "start": "2026-01-01",
            "end": "2026-01-08",
            "step": 2,
            "horizon": 2,
        },
    ).json()
    assert data["factor"] == "momentum_2d"
    assert "rank_ic" in data


class _FakeEtfFrame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        return self.rows


class _FakeAk:
    def fund_etf_hist_sina(self, symbol):
        # 30 天价格，够算趋势/回撤。
        return _FakeEtfFrame(
            [{"date": f"2026-01-{d:02d}", "close": 1.0 + 0.01 * d} for d in range(1, 31)]
        )


def test_instrument_analysis():
    store = MarketStore(":memory:")
    client = TestClient(create_app(store, provider=_FakeAk()))
    data = client.get("/api/instrument", params={"code": "513260"}).json()
    assert data["code"] == "513260"
    assert data["n"] == 30
    assert data["valuation"] is None  # 港股指数 PE 免费源不可得
    assert "max_drawdown" in data and "trend" in data
    assert "信号" in data["note"]  # 明确非买卖信号
    store.close()
