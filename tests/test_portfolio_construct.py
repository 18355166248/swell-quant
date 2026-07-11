import pytest

from swell_quant.factors.pipeline import CompositeResult
from swell_quant.portfolio.construct import equal_weight_top_n, portfolio_return


def test_equal_weight_top_n_picks_highest():
    result = CompositeResult(scores={"a": 1.0, "b": 3.0, "c": 2.0, "d": -1.0})
    w = equal_weight_top_n(result, 2)
    assert set(w) == {"b", "c"}  # 分最高的两只
    assert w["b"] == pytest.approx(0.5)
    assert w["c"] == pytest.approx(0.5)


def test_equal_weight_fewer_than_n():
    result = CompositeResult(scores={"a": 1.0, "b": None})
    w = equal_weight_top_n(result, 5)
    assert w == {"a": pytest.approx(1.0)}  # 只有 1 只可选 → 100%


def test_equal_weight_empty():
    assert equal_weight_top_n(CompositeResult(scores={"a": None}), 3) == {}


def test_portfolio_return_weighted():
    w = {"a": 0.5, "b": 0.5}
    assert portfolio_return(w, {"a": 0.10, "b": 0.20}) == pytest.approx(0.15)


def test_portfolio_return_renormalizes_on_missing():
    # b 收益缺失 → 只用 a，按可用权重归一（等于 a 的收益）。
    w = {"a": 0.5, "b": 0.5}
    assert portfolio_return(w, {"a": 0.10, "b": None}) == pytest.approx(0.10)


def test_portfolio_return_all_missing_is_none():
    assert portfolio_return({"a": 1.0}, {"a": None}) is None


def test_portfolio_return_empty_is_none():
    assert portfolio_return({}, {"a": 0.1}) is None
