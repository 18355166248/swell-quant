from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from datetime import date


def _ma(closes: Sequence[float], k: int) -> float | None:
    return statistics.fmean(closes[-k:]) if len(closes) >= k else None


def _trailing_return(closes: Sequence[float], k: int) -> float | None:
    if len(closes) <= k or closes[-k - 1] == 0:
        return None
    return closes[-1] / closes[-k - 1] - 1.0


def _percentile(sorted_values: Sequence[float], p: float) -> float:
    idx = min(len(sorted_values) - 1, int(p * len(sorted_values)))
    return sorted_values[idx]


def describe_prices(dates: Sequence[date], closes: Sequence[float]) -> dict:
    """把一段收盘价序列（按日期升序）算成描述性坐标。

    返回回撤/趋势/波动/收益分布等**历史事实**。少于约一年数据时部分字段为 None。
    **强调：这是历史坐标，不是买卖信号，不预测未来。**
    """

    if len(closes) < 2:
        raise ValueError("需要至少 2 个价格点")

    n = len(closes)
    current = closes[-1]
    ath = max(closes)
    ath_index = closes.index(ath)
    atl = min(closes)

    # 历史最大回撤（峰到谷）
    peak = closes[0]
    max_drawdown = 0.0
    for c in closes:
        peak = max(peak, c)
        if peak > 0:
            max_drawdown = min(max_drawdown, c / peak - 1.0)

    # 价在历史区间的位置（0=史低 1=史高）——注意：这是价格位置，**不是估值**
    range_percentile = sum(1 for c in closes if c <= current) / n

    ma = {k: _ma(closes, k) for k in (20, 60, 120, 250)}
    trend = {
        k: (None if v is None else ("above" if current > v else "below")) for k, v in ma.items()
    }
    trailing = {
        label: _trailing_return(closes, k)
        for label, k in (("m1", 20), ("m3", 60), ("m6", 120), ("m12", 250))
    }

    # 日收益、近 60 日年化波动及其历史分位
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, n) if closes[i - 1] != 0]
    ann_vol = None
    vol_percentile = None
    if len(rets) >= 60:

        def annualized(window: Sequence[float]) -> float:
            return statistics.pstdev(window) * math.sqrt(252)

        ann_vol = annualized(rets[-60:])
        rolling = [annualized(rets[i - 60 : i]) for i in range(60, len(rets) + 1)]
        vol_percentile = sum(1 for v in rolling if v <= ann_vol) / len(rolling)

    # 20 日滚动收益分布
    dist = None
    if n > 20:
        w20 = sorted(closes[i] / closes[i - 20] - 1.0 for i in range(20, n))
        dist = {
            "p5": _percentile(w20, 0.05),
            "p50": _percentile(w20, 0.50),
            "p95": _percentile(w20, 0.95),
            "min": w20[0],
            "max": w20[-1],
        }

    return {
        "start": str(dates[0]),
        "end": str(dates[-1]),
        "n": n,
        "current": current,
        "inception_return": current / closes[0] - 1.0 if closes[0] else None,
        "ath": ath,
        "ath_date": str(dates[ath_index]),
        "atl": atl,
        "drawdown_from_ath": current / ath - 1.0 if ath else None,
        "max_drawdown": max_drawdown,
        "range_percentile": range_percentile,
        "trend": trend,
        "trailing_returns": trailing,
        "ann_vol_60d": ann_vol,
        "vol_percentile": vol_percentile,
        "return_dist_20d": dist,
    }
