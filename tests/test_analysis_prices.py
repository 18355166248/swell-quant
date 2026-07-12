from datetime import date, timedelta

import pytest

from swell_quant.analysis.prices import describe_prices, valuation_percentile


def _series(closes):
    dates = [date(2022, 1, 1) + timedelta(days=i) for i in range(len(closes))]
    return dates, closes


def test_basic_fields():
    dates, closes = _series([1.0, 1.2, 0.9, 1.1])
    d = describe_prices(dates, closes)
    assert d["n"] == 4
    assert d["current"] == 1.1
    assert d["ath"] == 1.2
    assert d["atl"] == 0.9
    assert d["ath_date"] == str(dates[1])
    assert d["inception_return"] == pytest.approx(0.1)
    assert d["drawdown_from_ath"] == pytest.approx(1.1 / 1.2 - 1)


def test_max_drawdown_peak_to_trough():
    # 1 → 2(峰) → 1(谷) → 1.5：最大回撤 = 1/2 - 1 = -0.5
    dates, closes = _series([1.0, 2.0, 1.0, 1.5])
    assert describe_prices(dates, closes)["max_drawdown"] == pytest.approx(-0.5)


def test_range_percentile():
    dates, closes = _series([1.0, 2.0, 3.0, 4.0, 2.5])  # 当前 2.5 高于 1,2 → 3/5
    assert describe_prices(dates, closes)["range_percentile"] == pytest.approx(0.6)


def test_trend_above_below_ma():
    # 递增序列：当前价高于所有可算均线。
    dates, closes = _series([float(i) for i in range(1, 40)])
    trend = describe_prices(dates, closes)["trend"]
    assert trend[20] == "above"
    assert trend[250] is None  # 数据不足 250


def test_trailing_returns_and_none_when_short():
    dates, closes = _series([float(i) for i in range(1, 30)])  # 29 天
    tr = describe_prices(dates, closes)["trailing_returns"]
    assert tr["m1"] == pytest.approx(closes[-1] / closes[-21] - 1)
    assert tr["m3"] is None  # 不足 60


def test_vol_and_distribution_none_when_short():
    dates, closes = _series([1.0, 1.1, 1.05])  # 太短
    d = describe_prices(dates, closes)
    assert d["ann_vol_60d"] is None
    assert d["return_dist_20d"] is None


def test_distribution_present_with_enough_data():
    closes = [1.0 + 0.01 * (i % 7) for i in range(60)]  # 有波动
    dates, closes = _series(closes)
    dist = describe_prices(dates, closes)["return_dist_20d"]
    assert dist is not None
    assert dist["min"] <= dist["p50"] <= dist["max"]


def test_too_short_raises():
    with pytest.raises(ValueError):
        describe_prices([date(2022, 1, 1)], [1.0])


def test_valuation_percentile():
    # 当前值(最后)=15，历史 [10,20,30,15] → ≤15 的有 10,15 → 2/4 = 0.5
    v = valuation_percentile([10.0, 20.0, 30.0, 15.0])
    assert v["current"] == 15.0
    assert v["percentile"] == pytest.approx(0.5)
    assert v["min"] == 10.0 and v["max"] == 30.0
    assert v["median"] == pytest.approx(17.5)
    assert v["n"] == 4


def test_valuation_percentile_empty_raises():
    with pytest.raises(ValueError):
        valuation_percentile([])
