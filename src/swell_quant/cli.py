"""cli: 面向 AI/脚本的命令行入口，所有输出为 JSON。

与 HTTP API 共享 ``swell_quant.service`` 的研究服务层，保证同一套口径。
只依赖标准库 argparse；数据全部走 MarketStore 的 as_of / point-in-time 接口。

用法示例：
    swell-quant data summary
    swell-quant data bars --symbols 600519,000001 --as-of 2024-12-31 --lookback 20
    swell-quant data trade-days --start 2024-01-01 --end 2024-03-01
    swell-quant factor ic --name momentum --start 2024-03-01 --end 2024-12-01
    swell-quant backtest --factors '[{"name":"momentum","lookback":20}]' \
        --start 2024-03-01 --end 2024-12-01
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import date, datetime
from typing import Any

from swell_quant.marketdata.store import MarketStore
from swell_quant.service import FACTOR_CATALOG, run_backtest, run_factor_ic

DEFAULT_DB = "data/duckdb/marketdata.duckdb"


def _parse_date(day: str) -> date:
    return datetime.strptime(day, "%Y-%m-%d").date()


def _symbols(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def _jsonify(obj: Any) -> Any:
    """dataclass/date 递归转为可 JSON 序列化结构。"""

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonify(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, date):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    return obj


def _emit(payload: Any) -> None:
    json.dump(_jsonify(payload), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swell-quant",
        description="Swell Quant 研究 CLI（JSON 输出；仅用于研究，不构成投资建议）",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("SWELL_QUANT_DB", DEFAULT_DB),
        help=f"DuckDB 路径（默认 $SWELL_QUANT_DB 或 {DEFAULT_DB}）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # data 子命令组：只读查询，全部走 as_of/PIT 接口
    data = sub.add_parser("data", help="数据查询").add_subparsers(
        dest="data_command", required=True
    )

    data.add_parser("summary", help="库内数据概览")

    bars = data.add_parser("bars", help="日线（as_of + lookback）")
    bars.add_argument("--symbols", required=True, help="逗号分隔，如 600519,000001")
    bars.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    bars.add_argument("--lookback", type=int, default=20)
    bars.add_argument("--adjust", choices=["raw", "hfq"], default="raw", help="hfq=后复权")

    val = data.add_parser("valuation", help="估值（as_of 最近 N 条）")
    val.add_argument("--symbols", required=True)
    val.add_argument("--as-of", required=True)
    val.add_argument("--lookback", type=int, default=1)

    fund = data.add_parser("fundamentals", help="财务（point-in-time，只认已公告数据）")
    fund.add_argument("--symbols", required=True)
    fund.add_argument("--as-of", required=True)

    days = data.add_parser("trade-days", help="交易日序列")
    days.add_argument("--start", required=True)
    days.add_argument("--end", required=True)

    uni = data.add_parser("universe", help="指数成分池（as_of）")
    uni.add_argument("--index", default="000300")
    uni.add_argument("--as-of", default=None)

    # factor 子命令组
    factor = sub.add_parser("factor", help="因子").add_subparsers(
        dest="factor_command", required=True
    )
    factor.add_parser("catalog", help="可用因子目录")

    ic = factor.add_parser("ic", help="单因子多期 RankIC 评估")
    ic.add_argument("--name", required=True)
    ic.add_argument("--start", required=True)
    ic.add_argument("--end", required=True)
    ic.add_argument("--lookback", type=int, default=None)
    ic.add_argument("--item", default=None)
    ic.add_argument("--step", type=int, default=20)
    ic.add_argument("--horizon", type=int, default=20)
    ic.add_argument("--universe-index", default="000300")

    # backtest
    bt = sub.add_parser("backtest", help="多因子组合回测（Top-N 等权 + 成本 + 基准）")
    bt.add_argument(
        "--factors",
        required=True,
        help='JSON 数组，如 [{"name":"momentum","lookback":20,"weight":1.0}]',
    )
    bt.add_argument("--start", required=True)
    bt.add_argument("--end", required=True)
    bt.add_argument("--step", type=int, default=20)
    bt.add_argument("--horizon", type=int, default=20)
    bt.add_argument("--top-n", type=int, default=50)
    bt.add_argument("--cost-bps", type=float, default=10.0)
    bt.add_argument(
        "--benchmark", choices=["equal_weight", "index", "none"], default="equal_weight"
    )
    bt.add_argument("--benchmark-index", default="sh000300")
    bt.add_argument("--universe-index", default="000300")

    return parser


def _run_data(store: MarketStore, args: argparse.Namespace) -> Any:
    cmd = args.data_command
    if cmd == "summary":
        return store.summary()
    if cmd == "bars":
        getter = store.get_bars_hfq if args.adjust == "hfq" else store.get_bars
        records = getter(_symbols(args.symbols), _parse_date(args.as_of), args.lookback)
        return {"adjust": args.adjust, "count": len(records), "bars": records}
    if cmd == "valuation":
        records = store.get_valuations(
            _symbols(args.symbols), _parse_date(args.as_of), lookback=args.lookback
        )
        return {"count": len(records), "valuations": records}
    if cmd == "fundamentals":
        records = store.get_fundamentals(_symbols(args.symbols), _parse_date(args.as_of))
        return {"count": len(records), "fundamentals": records}
    if cmd == "trade-days":
        days = store.trading_days(_parse_date(args.start), _parse_date(args.end))
        return {"count": len(days), "trading_days": days}
    if cmd == "universe":
        target = _parse_date(args.as_of) if args.as_of else datetime.now().date()
        symbols = store.get_universe(args.index, target, approximate_from_latest=True)
        return {"index": args.index, "as_of": target, "count": len(symbols), "symbols": symbols}
    raise ValueError(f"未知 data 子命令：{cmd}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "factor" and args.factor_command == "catalog":
            _emit({"catalog": FACTOR_CATALOG})
            return 0
        with MarketStore(args.db) as store:
            if args.command == "data":
                _emit(_run_data(store, args))
            elif args.command == "factor":  # ic
                _emit(
                    run_factor_ic(
                        store,
                        name=args.name,
                        start=_parse_date(args.start),
                        end=_parse_date(args.end),
                        lookback=args.lookback,
                        item=args.item,
                        step=args.step,
                        horizon=args.horizon,
                        universe_index=args.universe_index,
                    )
                )
            elif args.command == "backtest":
                _emit(
                    run_backtest(
                        store,
                        factors=json.loads(args.factors),
                        start=_parse_date(args.start),
                        end=_parse_date(args.end),
                        step=args.step,
                        horizon=args.horizon,
                        top_n=args.top_n,
                        cost_bps=args.cost_bps,
                        benchmark=args.benchmark,
                        benchmark_index=args.benchmark_index,
                        universe_index=args.universe_index,
                    )
                )
        return 0
    except (ValueError, json.JSONDecodeError) as error:
        # 参数/口径错误：JSON 报错到 stderr，退出码 2，方便 AI/脚本判别
        json.dump({"error": str(error)}, sys.stderr, ensure_ascii=False)
        sys.stderr.write("\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
