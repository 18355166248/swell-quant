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


def neutralize_against(values: FactorValues, covariate: FactorValues) -> FactorValues:
    """对连续协变量做截面中性化：回归 ``value = a + b*cov`` 取残差。

    用于剥离因子里的规模等暴露（如 cov = log 市值）——残差是“同规模内”的纯因子。
    只用 value 与 cov 都非缺的票；协变量无离散度时退化为去均值。任一缺失记 None。
    """

    paired = [(v, covariate.get(s)) for s, v in values.items() if v is not None]
    paired = [(v, c) for v, c in paired if c is not None]
    if len(paired) < 2:
        return dict(values)
    ys = [v for v, _ in paired]
    xs = [c for _, c in paired]
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    var_x = statistics.pvariance(xs)
    if var_x == 0:
        slope = 0.0
    else:
        cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
        slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x
    return {
        symbol: (
            None
            if value is None or covariate.get(symbol) is None
            else value - (intercept + slope * covariate[symbol])
        )
        for symbol, value in values.items()
    }


def neutralize_by_group(values: FactorValues, groups: dict[str, str]) -> FactorValues:
    """对分类分组做截面中性化：减去所在组的均值（如按行业去均值）。

    剥离行业等暴露——结果是“同组内”的相对强弱。无分组或值缺失的票记 None。
    """

    group_values: dict[str, list[float]] = {}
    for symbol, value in values.items():
        group = groups.get(symbol)
        if value is not None and group is not None:
            group_values.setdefault(group, []).append(value)
    group_mean = {g: statistics.fmean(vs) for g, vs in group_values.items()}
    return {
        symbol: (
            value - group_mean[groups[symbol]]
            if value is not None and groups.get(symbol) in group_mean
            else None
        )
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
