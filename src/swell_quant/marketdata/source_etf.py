from __future__ import annotations

from datetime import date
from typing import Any

from swell_quant.marketdata.frames import iter_rows, parse_date, to_float, value


class EtfSourceError(RuntimeError):
    pass


def etf_sina_symbol(code: str) -> str:
    """ETF 6 位代码 → 新浪格式：沪市(5 开头)= sh，深市(1 开头)= sz。"""

    digits = code.split(".")[0].strip()[-6:]
    if digits.startswith("5"):
        return f"sh{digits}"
    if digits.startswith("1"):
        return f"sz{digits}"
    raise ValueError(f"无法判断 ETF 交易所前缀：{code}")


def fetch_etf_bars_sina(code: str, provider: Any) -> list[tuple[date, float]]:
    """从新浪拉 ETF 日线，返回 (日期, 收盘) 升序列表。

    ``provider`` 需提供 ``fund_etf_hist_sina(symbol)``（真实为 akshare，测试注入 Fake）。
    """

    frame = provider.fund_etf_hist_sina(symbol=etf_sina_symbol(code))
    series = [
        (parse_date(value(row, "date", "日期")), to_float(value(row, "close", "收盘")))
        for row in iter_rows(frame)
    ]
    series.sort(key=lambda item: item[0])
    if not series:
        raise EtfSourceError(f"新浪返回 ETF {code} 无数据")
    return series
