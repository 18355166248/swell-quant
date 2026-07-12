"""factors: 因子层，消费 marketdata（按 as_of 查询，无未来函数）。

每个因子在给定 as_of 与股票池上，产出每只票一个截面因子值（数据不足则 None）。
因子只经 MarketStore 的 as_of 接口取数，天然继承“防未来函数”。
"""

from swell_quant.factors.base import Factor
from swell_quant.factors.momentum import MomentumFactor
from swell_quant.factors.quality import QualityFactor
from swell_quant.factors.reversal import ReversalFactor
from swell_quant.factors.value import ValueFactor
from swell_quant.factors.volatility import VolatilityFactor
from swell_quant.factors.preprocess import (
    fill_missing,
    neutralize_against,
    neutralize_by_group,
    standardize,
    winsorize_mad,
    zscore,
)
from swell_quant.factors.pipeline import (
    CompositeResult,
    FactorPipeline,
    FactorWeight,
)
from swell_quant.factors.evaluate import (
    ICResult,
    ICSummary,
    PeriodIC,
    SeriesStats,
    evaluate_factor,
    evaluate_factor_series,
    forward_returns,
    information_coefficient,
    rank_ic,
    sample_as_of_dates,
)

__all__ = [
    "CompositeResult",
    "Factor",
    "FactorPipeline",
    "FactorWeight",
    "ICResult",
    "ICSummary",
    "MomentumFactor",
    "PeriodIC",
    "QualityFactor",
    "ReversalFactor",
    "SeriesStats",
    "ValueFactor",
    "VolatilityFactor",
    "evaluate_factor",
    "evaluate_factor_series",
    "fill_missing",
    "forward_returns",
    "information_coefficient",
    "neutralize_against",
    "neutralize_by_group",
    "rank_ic",
    "sample_as_of_dates",
    "standardize",
    "winsorize_mad",
    "zscore",
]
