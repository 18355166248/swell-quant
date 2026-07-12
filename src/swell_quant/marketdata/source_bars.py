from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from swell_quant.marketdata.frames import iter_rows as _iter_rows
from swell_quant.marketdata.frames import parse_date as _parse_date
from swell_quant.marketdata.frames import to_float as _to_float
from swell_quant.marketdata.frames import value as _value
from swell_quant.marketdata.records import BarRecord


class BarSourceError(RuntimeError):
    pass


def build_bar_records(
    symbol: str,
    raw_rows: Iterable[dict[str, Any]],
    hfq_rows: Iterable[dict[str, Any]],
    source: str,
) -> list[BarRecord]:
    """把“不复权行情 + 后复权行情”合成标准 BarRecord。

    OHLC/成交量/成交额取自**不复权**行情（客观真实价）。
    ``adj_factor[t] = 后复权收盘[t] / 不复权收盘[t]`` —— 这是**上市日锚定**、
    对未来分红免疫的因子（见 docs/data-module-decisions.md §7-A）。因此此处
    **不**做按批次的重锚定：hfq/raw 比值天生跨批次一致。

    只有两侧都存在、且不复权收盘 > 0 的交易日才产出记录。
    """

    hfq_close_by_date = {
        _parse_date(_value(row, "日期", "date")): _to_float(_value(row, "收盘", "close"))
        for row in hfq_rows
    }

    records: list[BarRecord] = []
    for row in raw_rows:
        trade_date = _parse_date(_value(row, "日期", "date"))
        raw_close = _to_float(_value(row, "收盘", "close"))
        hfq_close = hfq_close_by_date.get(trade_date)
        if hfq_close is None or raw_close <= 0:
            # 缺 hfq 对齐或收盘异常的交易日不入库，避免把脏因子写进事实表。
            continue
        records.append(
            BarRecord(
                symbol=symbol,
                date=trade_date,
                open=_to_float(_value(row, "开盘", "open")),
                high=_to_float(_value(row, "最高", "high")),
                low=_to_float(_value(row, "最低", "low")),
                close=raw_close,
                volume=int(_to_float(_value(row, "成交量", "volume"))),
                amount=_to_float(_value(row, "成交额", "amount")),
                adj_factor=hfq_close / raw_close,
                source=source,
            )
        )
    records.sort(key=lambda bar: bar.date)
    return records


def build_bars_from_factor_steps(
    symbol: str,
    raw_rows: Iterable[dict[str, Any]],
    factor_steps: Iterable[dict[str, Any]],
    source: str,
) -> list[BarRecord]:
    """用**不复权行情 + 稀疏台阶因子**合成 BarRecord（推荐实现，见 §7-A）。

    ``factor_steps`` 是 ``ak.stock_zh_a_daily(adjust="hfq-factor")`` 的返回：仅在
    每个除权日各一行（含上市日 = 1.0）。任意交易日的因子 = **前向填充**——取
    ``step_date <= trade_date`` 的最近一条。相比 hfq/raw 相除，此法精确、无浮点
    噪声，因此幂等 upsert 安全。
    """

    steps = sorted(
        (
            (_parse_date(_value(row, "date", "日期")), _to_float(_value(row, "hfq_factor")))
            for row in factor_steps
        ),
        key=lambda item: item[0],
    )
    if not steps:
        raise BarSourceError(f"{symbol} 无 hfq-factor 台阶数据")

    records: list[BarRecord] = []
    for row in raw_rows:
        trade_date = _parse_date(_value(row, "日期", "date"))
        raw_close = _to_float(_value(row, "收盘", "close"))
        factor = _forward_fill_factor(steps, trade_date)
        if factor is None or raw_close <= 0:
            # 交易日早于任何因子台阶（异常）或收盘异常，不入事实表。
            continue
        records.append(
            BarRecord(
                symbol=symbol,
                date=trade_date,
                open=_to_float(_value(row, "开盘", "open")),
                high=_to_float(_value(row, "最高", "high")),
                low=_to_float(_value(row, "最低", "low")),
                close=raw_close,
                volume=int(_to_float(_value(row, "成交量", "volume"))),
                amount=_to_float(_value(row, "成交额", "amount")),
                adj_factor=factor,
                source=source,
            )
        )
    records.sort(key=lambda bar: bar.date)
    return records


def _forward_fill_factor(steps: list[tuple[date, float]], trade_date: date) -> float | None:
    """取 step_date <= trade_date 的最近一个因子（steps 已按日期升序）。"""

    factor: float | None = None
    for step_date, value in steps:
        if step_date <= trade_date:
            factor = value
        else:
            break
    return factor


def fetch_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    provider: Any,
    source: str = "akshare",
) -> list[BarRecord]:
    """从 provider 拉取不复权与后复权两份日线，合成 BarRecord。

    ``provider`` 需提供 ``stock_zh_a_hist(symbol, period, start_date, end_date, adjust)``
    （真实为 akshare 模块，测试注入 Fake）。分两次调用（adjust="" 与 "hfq"），
    因为只有二者相除才能得到客观、免疫未来函数的复权因子。
    """

    raw_frame = provider.stock_zh_a_hist(
        symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=""
    )
    hfq_frame = provider.stock_zh_a_hist(
        symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="hfq"
    )
    records = build_bar_records(symbol, _iter_rows(raw_frame), _iter_rows(hfq_frame), source)
    if not records:
        raise BarSourceError(f"{source} 返回 {symbol} 无可用日线（不复权/后复权对齐后为空）")
    return records


def sina_symbol(code: str) -> str:
    """6 位代码 → 新浪格式 "sh600519" / "sz000001" / "bj830799"。

    新浪 stock_zh_a_daily 要求“小写交易所前缀 + 6 位代码”。
    """

    digits = code.split(".")[0].strip()[-6:]
    if digits.startswith(("60", "68", "90")):
        prefix = "sh"
    elif digits.startswith(("00", "30", "20")):
        prefix = "sz"
    elif digits.startswith(("43", "83", "87", "88")):
        prefix = "bj"
    else:
        raise ValueError(f"无法判断交易所前缀：{code}")
    return f"{prefix}{digits}"


def fetch_bars_sina(
    symbol: str,
    start_date: str,
    end_date: str,
    provider: Any,
    source: str = "sina",
) -> list[BarRecord]:
    """从**新浪**拉取不复权日线 + hfq 台阶因子，合成 BarRecord（推荐真实路径）。

    ``provider`` 需提供 ``stock_zh_a_daily(symbol, start_date, end_date, adjust)``
    （真实为 akshare 模块，测试注入 Fake）。不复权行情用 ``adjust=""``；因子用
    ``adjust="hfq-factor"``（稀疏台阶、上市日锚定、高精度），二者经前向填充合成。
    本机东方财富被代理封禁，新浪是可用的真实源（见 memory / §7-A）。
    """

    sina = sina_symbol(symbol)
    raw_frame = provider.stock_zh_a_daily(
        symbol=sina, start_date=start_date, end_date=end_date, adjust=""
    )
    # hfq-factor 返回全历史稀疏台阶，不吃 start/end；前向填充时自动覆盖窗口内每天。
    factor_frame = provider.stock_zh_a_daily(symbol=sina, adjust="hfq-factor")
    records = build_bars_from_factor_steps(
        symbol, _iter_rows(raw_frame), _iter_rows(factor_frame), source
    )
    if not records:
        raise BarSourceError(f"{source} 返回 {symbol} 无可用日线")
    return records
