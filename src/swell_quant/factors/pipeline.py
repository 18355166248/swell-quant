from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from swell_quant.factors.base import Factor, FactorValues
from swell_quant.factors.preprocess import standardize
from swell_quant.marketdata.store import MarketStore


@dataclass(frozen=True)
class FactorWeight:
    factor: Factor
    weight: float = 1.0


@dataclass(frozen=True)
class CompositeResult:
    scores: FactorValues  # 综合分；全部因子都缺的票记 None

    def ranking(self) -> list[tuple[str, float]]:
        """按综合分降序（同分按 symbol 升序稳定）；None 分的票不参与排名。"""

        scored = [(s, v) for s, v in self.scores.items() if v is not None]
        return sorted(scored, key=lambda item: (-item[1], item[0]))


@dataclass(frozen=True)
class FactorPipeline:
    """多因子合成：各因子 compute → 截面标准化 → 加权求和 → 综合分/排名。

    每个因子先 z-score 到同尺度再加权，故权重直接可比。某票在某因子上缺失（None）时，
    该因子对它贡献 0（中性，等于截面均值），其余因子照常加权；**所有**因子都缺的票综合分记
    None、排除出排名，避免把“无数据”误当成“中庸”。
    """

    weights: tuple[FactorWeight, ...]
    n_mad: float = 3.0

    def compute(
        self, store: MarketStore, symbols: Sequence[str], as_of: date
    ) -> CompositeResult:
        standardized: list[tuple[FactorValues, float]] = []
        for factor_weight in self.weights:
            raw = factor_weight.factor.compute(store, symbols, as_of)
            standardized.append((standardize(raw, n_mad=self.n_mad), factor_weight.weight))

        scores: FactorValues = {}
        for symbol in symbols:
            total = 0.0
            any_present = False
            for values, weight in standardized:
                value = values.get(symbol)
                if value is not None:
                    total += weight * value
                    any_present = True
            scores[symbol] = total if any_present else None
        return CompositeResult(scores=scores)
