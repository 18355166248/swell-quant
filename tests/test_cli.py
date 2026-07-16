"""CLI 入口测试：写一个临时 DuckDB，走 main() 全链路验证 JSON 输出。"""

import json
from datetime import date, timedelta

import pytest

from swell_quant.cli import main
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
def db_path(tmp_path):
    path = tmp_path / "cli.duckdb"
    with MarketStore(path) as store:
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
    return str(path)


def _run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured


def test_data_summary(db_path, capsys):
    code, out = _run(capsys, "--db", db_path, "data", "summary")
    assert code == 0
    data = json.loads(out.out)
    assert data["bars"]["symbols"] == 3


def test_data_bars_as_of(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "data",
        "bars",
        "--symbols",
        "a,b",
        "--as-of",
        "2026-01-05",
        "--lookback",
        "3",
    )
    assert code == 0
    data = json.loads(out.out)
    assert data["count"] == 6  # 2 只票 × 3 天
    # as_of 保证：没有任何一条晚于 as_of（无未来函数）
    assert all(bar["date"] <= "2026-01-05" for bar in data["bars"])


def test_data_trade_days(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "data",
        "trade-days",
        "--start",
        "2026-01-01",
        "--end",
        "2026-01-05",
    )
    assert code == 0
    data = json.loads(out.out)
    assert data["count"] == 5
    assert data["trading_days"][0] == "2026-01-01"


def test_data_universe(db_path, capsys):
    code, out = _run(
        capsys, "--db", db_path, "data", "universe", "--index", "000300", "--as-of", "2026-01-10"
    )
    assert code == 0
    data = json.loads(out.out)
    assert set(data["symbols"]) == {"a", "b", "c"}


def test_factor_catalog(db_path, capsys):
    code, out = _run(capsys, "factor", "catalog")
    assert code == 0
    names = {f["name"] for f in json.loads(out.out)["catalog"]}
    assert {"momentum", "reversal", "value", "quality", "volatility"} <= names


def test_factor_ic(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "factor",
        "ic",
        "--name",
        "momentum",
        "--lookback",
        "2",
        "--start",
        "2026-01-03",
        "--end",
        "2026-01-08",
        "--step",
        "2",
        "--horizon",
        "2",
    )
    assert code == 0
    data = json.loads(out.out)
    assert data["factor"] == "momentum_2d"
    assert "rank_ic" in data
    assert "研究" in data["note"]


def test_backtest(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "backtest",
        "--factors",
        '[{"name":"momentum","lookback":2}]',
        "--start",
        "2026-01-03",
        "--end",
        "2026-01-08",
        "--step",
        "2",
        "--horizon",
        "2",
        "--top-n",
        "1",
    )
    assert code == 0
    data = json.loads(out.out)
    assert data["periods"] >= 1
    assert "total_return" in data["metrics"]
    assert "研究" in data["note"]


def test_backtest_walk_forward(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "backtest",
        "--factors",
        '[{"name":"momentum","lookback":2}]',
        "--start",
        "2026-01-03",
        "--end",
        "2026-01-08",
        "--step",
        "2",
        "--horizon",
        "2",
        "--top-n",
        "1",
        "--walk-forward",
        "--train-size",
        "1",
    )
    assert code == 0
    data = json.loads(out.out)
    assert data["train_size"] == 1
    assert data["oos_periods"] >= 1
    # 每个因子都要有样本外 RankIC 统计
    assert "momentum_2d" in data["oos_rank_ic"]
    assert "total_return" in data["metrics"]
    assert "研究" in data["note"]


def test_backtest_walk_forward_train_too_big_exit_2(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "backtest",
        "--factors",
        '[{"name":"momentum","lookback":2}]',
        "--start",
        "2026-01-03",
        "--end",
        "2026-01-08",
        "--step",
        "2",
        "--horizon",
        "2",
        "--walk-forward",
        "--train-size",
        "99",
    )
    assert code == 2
    assert "训练窗" in json.loads(out.err)["error"]


def test_unknown_factor_exit_2(db_path, capsys):
    code, out = _run(
        capsys,
        "--db",
        db_path,
        "factor",
        "ic",
        "--name",
        "nope",
        "--start",
        "2026-01-03",
        "--end",
        "2026-01-08",
    )
    assert code == 2
    assert "未知因子" in json.loads(out.err)["error"]
