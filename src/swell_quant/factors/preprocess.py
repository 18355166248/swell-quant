from __future__ import annotations

import statistics

from swell_quant.factors.base import FactorValues

# 预处理把原始因子截面拉成“可比、可组合”的形态。每个变换都是 FactorValues -> FactorValues，
# 可自由串联。None（数据不足）不参与统计，默认原样保留，由调用方决定是否最后填充。

# MAD 到标准差的一致性系数（正态分布下 1.4826*MAD ≈ std）。
_MAD_TO_STD = 1.4826


def winsorize_mad(values: FactorValues, n_mad: float = 3.0) -> FactorValues:
    """基于 MAD 的去极值：把偏离中位数超过 ``n_mad`` 个（尺度化）MAD 的值截断到边界。

    MAD 比标准差更抗异常值，是 A 股因子常用的去极值法。无离散度（MAD=0）时不裁剪。
    """

    present = [v for v in values.values() if v is not None]
    if not present:
        return dict(values)
    median = statistics.median(present)
    mad = statistics.median([abs(v - median) for v in present])
    scaled = _MAD_TO_STD * mad
    if scaled == 0:
        return dict(values)  # 截面无离散度，裁剪没有意义
    low, high = median - n_mad * scaled, median + n_mad * scaled
    return {
        symbol: (None if value is None else min(max(value, low), high))
        for symbol, value in values.items()
    }


def zscore(values: FactorValues) -> FactorValues:
    """截面标准化：``(x - mean) / std``（总体标准差）。截面无离散度时全记 0。"""

    present = [v for v in values.values() if v is not None]
    if not present:
        return dict(values)
    mean = statistics.fmean(present)
    std = statistics.pstdev(present)
    return {
        symbol: (None if value is None else (0.0 if std == 0 else (value - mean) / std))
        for symbol, value in values.items()
    }


def fill_missing(values: FactorValues, fill: float = 0.0) -> FactorValues:
    """把 None 填成 ``fill``（z-score 后填 0，即用截面均值兜底缺失）。"""

    return {symbol: (fill if value is None else value) for symbol, value in values.items()}


def standardize(
    values: FactorValues, n_mad: float = 3.0, fill_value: float | None = None
) -> FactorValues:
    """去极值 → z-score 的常用流水线；``fill_value`` 非 None 时再填充缺失。"""

    out = zscore(winsorize_mad(values, n_mad))
    if fill_value is not None:
        out = fill_missing(out, fill_value)
    return out
