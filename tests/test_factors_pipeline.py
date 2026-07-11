from datetime import date

import pytest

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.factors.pipeline import CompositeResult, FactorPipeline, FactorWeight


class FakeFactor(Factor):
    """返回预设截面值的假因子，用于隔离测试合成逻辑（不依赖 store）。"""

    def __init__(self, name, values):
        self._name = name
        self._values = values

    @property
    def name(self):
        return self._name

    def compute(self, store, symbols, as_of) -> FactorValues:
        return {s: self._values.get(s) for s in symbols}


AS_OF = date(2026, 1, 1)
SYMBOLS = ["a", "b", "c"]


def test_single_factor_ranking_matches_values():
    f = FakeFactor("f", {"a": 1.0, "b": 2.0, "c": 3.0})
    result = FactorPipeline(weights=(FactorWeight(f),)).compute(None, SYMBOLS, AS_OF)
    assert [s for s, _ in result.ranking()] == ["c", "b", "a"]  # 值大者靠前


def test_two_factors_weighted_sum():
    # 两因子标准化后加权求和。构造对称值便于验证。
    f1 = FakeFactor("f1", {"a": 1.0, "b": 2.0, "c": 3.0})
    f2 = FakeFactor("f2", {"a": 3.0, "b": 2.0, "c": 1.0})  # 与 f1 反向
    pipe = FactorPipeline(weights=(FactorWeight(f1, 1.0), FactorWeight(f2, 1.0)))
    result = pipe.compute(None, SYMBOLS, AS_OF)
    # f1 与 f2 反向、等权 → 三票综合分应相等（都为 0）。
    assert result.scores["a"] == pytest.approx(0.0)
    assert result.scores["b"] == pytest.approx(0.0)
    assert result.scores["c"] == pytest.approx(0.0)


def test_weight_tilts_result():
    f1 = FakeFactor("f1", {"a": 1.0, "b": 2.0, "c": 3.0})
    f2 = FakeFactor("f2", {"a": 3.0, "b": 2.0, "c": 1.0})
    # f1 权重更大 → 综合分应跟随 f1（c 最高）。
    pipe = FactorPipeline(weights=(FactorWeight(f1, 2.0), FactorWeight(f2, 1.0)))
    result = pipe.compute(None, SYMBOLS, AS_OF)
    assert [s for s, _ in result.ranking()] == ["c", "b", "a"]


def test_missing_factor_contributes_neutral_zero():
    f1 = FakeFactor("f1", {"a": 1.0, "b": 2.0, "c": 3.0})
    f2 = FakeFactor("f2", {"a": 1.0, "b": 2.0})  # c 在 f2 缺失
    pipe = FactorPipeline(weights=(FactorWeight(f1), FactorWeight(f2)))
    result = pipe.compute(None, SYMBOLS, AS_OF)
    # c 有 f1 的值、f2 缺（贡献 0）→ c 仍有分、不为 None。
    assert result.scores["c"] is not None


def test_all_missing_symbol_is_none_and_excluded():
    f1 = FakeFactor("f1", {"a": 1.0, "b": 2.0})  # c 全缺
    f2 = FakeFactor("f2", {"a": 1.0, "b": 2.0})
    pipe = FactorPipeline(weights=(FactorWeight(f1), FactorWeight(f2)))
    result = pipe.compute(None, SYMBOLS, AS_OF)
    assert result.scores["c"] is None
    assert "c" not in [s for s, _ in result.ranking()]


def test_ranking_excludes_none_and_sorts_desc():
    result = CompositeResult(scores={"a": -1.0, "b": 2.0, "c": None, "d": 0.5})
    assert result.ranking() == [("b", 2.0), ("d", 0.5), ("a", -1.0)]
