import statistics

import pytest

from swell_quant.factors.preprocess import (
    fill_missing,
    standardize,
    winsorize_mad,
    zscore,
)


def test_winsorize_clips_outlier():
    # 一堆 1..5 加一个极端值 100；100 应被拉回上界，正常值不动。
    values = {f"s{i}": float(i) for i in range(1, 6)}
    values["out"] = 100.0
    out = winsorize_mad(values, n_mad=3.0)
    assert out["out"] < 100.0  # 被截断
    assert out["s1"] == 1.0 and out["s3"] == 3.0  # 正常值不变


def test_winsorize_zero_mad_passthrough():
    values = {"a": 5.0, "b": 5.0, "c": 5.0}
    assert winsorize_mad(values) == values


def test_winsorize_preserves_none():
    out = winsorize_mad({"a": 1.0, "b": None, "c": 100.0})
    assert out["b"] is None


def test_zscore_mean_zero_std_one():
    values = {f"s{i}": float(i) for i in range(1, 6)}  # 1..5
    out = zscore(values)
    present = [v for v in out.values() if v is not None]
    assert statistics.fmean(present) == pytest.approx(0.0, abs=1e-9)
    assert statistics.pstdev(present) == pytest.approx(1.0, abs=1e-9)


def test_zscore_specific_value():
    out = zscore({"a": 1.0, "b": 2.0, "c": 3.0})
    # mean=2, pstdev=sqrt(2/3)
    assert out["c"] == pytest.approx((3 - 2) / statistics.pstdev([1, 2, 3]))


def test_zscore_excludes_none_from_stats_and_preserves_it():
    out = zscore({"a": 1.0, "b": 3.0, "missing": None})
    # 统计只用 [1,3]，mean=2 → a 和 b 对称。
    assert out["a"] == pytest.approx(-out["b"])
    assert out["missing"] is None


def test_zscore_no_dispersion_all_zero():
    out = zscore({"a": 5.0, "b": 5.0})
    assert out == {"a": 0.0, "b": 0.0}


def test_all_none_passthrough():
    values = {"a": None, "b": None}
    assert winsorize_mad(values) == values
    assert zscore(values) == values


def test_fill_missing():
    assert fill_missing({"a": 1.5, "b": None}) == {"a": 1.5, "b": 0.0}
    assert fill_missing({"a": None}, fill=-1.0) == {"a": -1.0}


def test_standardize_pipeline_winsorizes_then_zscores():
    values = {f"s{i}": float(i) for i in range(1, 6)}
    values["out"] = 100.0
    plain = zscore(values)
    robust = standardize(values, n_mad=3.0)
    # 去极值后离群点对 std 的拉动变小，正常值的 z 分更大（更可比）。
    assert abs(robust["s1"]) > abs(plain["s1"])


def test_standardize_fill_value_fills_none():
    out = standardize({"a": 1.0, "b": 2.0, "c": None}, fill_value=0.0)
    assert out["c"] == 0.0
    assert out["a"] is not None
