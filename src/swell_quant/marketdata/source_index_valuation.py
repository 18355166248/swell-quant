from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any


class IndexValuationSourceError(RuntimeError):
    pass


# 蛋卷（雪球）估值中心的指数 PE 历史，全量。恒生科技 = HKHSTECH、沪深300 = SH000300 等。
DANJUAN_PE_URL = "https://danjuanfunds.com/djapi/index_eva/pe_history/{index}?day=all"

# 东八区：蛋卷时间戳转交易日用。
_CST = timezone(timedelta(hours=8))


def _default_get(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://danjuanfunds.com/"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - 固定可信域名
        return json.load(response)


def fetch_index_valuation_danjuan(
    index_code: str, http_get: Callable[[str], Any] = _default_get
) -> list[tuple[date, float]]:
    """拉某指数的**全量 PE 历史**（蛋卷/雪球估值中心，公开数据），返回 (日期, PE) 升序。

    ``index_code`` 用蛋卷代码，如恒生科技 = "HKHSTECH"。``http_get`` 可注入（测试用）。
    """

    data = http_get(DANJUAN_PE_URL.format(index=index_code))
    try:
        points = data["data"]["index_eva_pe_growths"]
    except (KeyError, TypeError) as error:
        raise IndexValuationSourceError(f"蛋卷返回结构异常：{index_code}") from error

    series = [
        (datetime.fromtimestamp(point["ts"] / 1000, _CST).date(), float(point["pe"]))
        for point in points
        if point.get("pe") is not None
    ]
    series.sort(key=lambda item: item[0])
    if not series:
        raise IndexValuationSourceError(f"蛋卷返回 {index_code} 无 PE 数据")
    return series
