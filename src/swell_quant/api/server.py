from __future__ import annotations

import threading
from datetime import date, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from swell_quant.factors import (
    FactorPipeline,
    FactorWeight,
    MomentumFactor,
    QualityFactor,
    ReversalFactor,
    ValueFactor,
    VolatilityFactor,
    evaluate_factor_series,
    sample_as_of_dates,
)
from swell_quant.analysis import describe_prices, valuation_percentile
from swell_quant.factors.base import Factor
from swell_quant.marketdata.source_etf import EtfSourceError, fetch_etf_bars_sina
from swell_quant.marketdata.store import MarketStore
from swell_quant.portfolio import backtest_composite

# 因子目录：看板从这里渲染可选因子。lookback 用于价量因子，item 用于财务/估值因子。
FACTOR_CATALOG = [
    {"name": "momentum", "label": "动量", "param": "lookback", "default": 20},
    {"name": "reversal", "label": "短期反转", "param": "lookback", "default": 5},
    {"name": "volatility", "label": "波动率(低波给负权重)", "param": "lookback", "default": 20},
    {"name": "value", "label": "价值(1/估值)", "param": "item", "default": "pe_ttm"},
    {"name": "quality", "label": "质量/成长", "param": "item", "default": "roe"},
]


class FactorSpec(BaseModel):
    name: str
    lookback: int | None = None
    item: str | None = None
    weight: float = 1.0


class ValuationPoint(BaseModel):
    date: str  # YYYY-MM-DD
    value: float


class ValuationUpload(BaseModel):
    code: str
    item: str = "pe_ttm"
    source: str = "user"
    points: list[ValuationPoint] = Field(min_length=1)


class BacktestRequest(BaseModel):
    factors: list[FactorSpec] = Field(min_length=1)
    start: str  # YYYY-MM-DD
    end: str
    step: int = 20
    horizon: int = 20
    top_n: int = 50
    cost_bps: float = 10.0
    benchmark: str = "equal_weight"  # equal_weight | index | none
    benchmark_index: str = "sh000300"
    universe_index: str | None = "000300"


def _build_factor(spec: FactorSpec) -> Factor:
    if spec.name == "momentum":
        return MomentumFactor(spec.lookback or 20)
    if spec.name == "reversal":
        return ReversalFactor(spec.lookback or 5)
    if spec.name == "volatility":
        return VolatilityFactor(spec.lookback or 20)
    if spec.name == "value":
        return ValueFactor(spec.item or "pe_ttm")
    if spec.name == "quality":
        return QualityFactor(spec.item or "roe")
    raise HTTPException(status_code=400, detail=f"未知因子：{spec.name}")


def _parse(day: str) -> date:
    return datetime.strptime(day, "%Y-%m-%d").date()


def create_app(store: MarketStore, provider: object | None = None) -> FastAPI:
    """构建 FastAPI 应用。``store`` 为已打开的 MarketStore（测试传内存库）。

    ``provider`` 为行情提供者（真实为 akshare，用于 ETF 实时研究；为 None 时按需
    懒加载 akshare）。DuckDB 连接非线程安全，用锁串行化——个人单用户看板足够。
    """

    app = FastAPI(title="Swell Quant API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 个人本地看板；只读接口
        allow_methods=["*"],
        allow_headers=["*"],
    )
    lock = threading.Lock()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/meta")
    def meta() -> dict:
        with lock:
            return store.summary()

    @app.get("/api/factors")
    def factors() -> dict:
        return {"catalog": FACTOR_CATALOG}

    @app.get("/api/universe")
    def universe(index: str = "000300", as_of: str | None = None) -> dict:
        target = _parse(as_of) if as_of else datetime.now().date()
        with lock:
            symbols = store.get_universe(index, target, approximate_from_latest=True)
        return {"index": index, "as_of": str(target), "count": len(symbols), "symbols": symbols}

    @app.post("/api/backtest")
    def backtest(req: BacktestRequest) -> dict:
        weights = tuple(FactorWeight(_build_factor(s), s.weight) for s in req.factors)
        pipeline = FactorPipeline(weights=weights)
        with lock:
            dates = sample_as_of_dates(store, _parse(req.start), _parse(req.end), step=req.step)
            if len(dates) < 2:
                raise HTTPException(status_code=400, detail="日期区间内交易日不足")
            result = backtest_composite(
                pipeline,
                store,
                [],
                dates,
                top_n=req.top_n,
                horizon=req.horizon,
                universe_index=req.universe_index,
                benchmark_index=req.benchmark_index if req.benchmark == "index" else None,
                equal_weight_benchmark=req.benchmark == "equal_weight",
                cost_bps=req.cost_bps,
            )
        ppy = 252 / req.horizon
        curve = [{"date": str(d), "equity": round(e, 6)} for d, e in result.equity_curve]
        return {
            "periods": len(result.periods),
            "metrics": {
                "total_return": result.total_return,
                "annualized_return": result.annualized_return(ppy),
                "annualized_sharpe": result.annualized_sharpe(ppy),
                "information_ratio": result.information_ratio,
                "excess_hit_rate": result.excess_hit_rate,
                "benchmark_total_return": result.benchmark_total_return,
                "max_drawdown": result.max_drawdown,
                "total_cost": result.total_cost,
            },
            "equity_curve": curve,
        }

    @app.get("/api/factor-ic")
    def factor_ic(
        name: str,
        start: str,
        end: str,
        lookback: int | None = None,
        item: str | None = None,
        step: int = 20,
        horizon: int = 20,
        universe_index: str = "000300",
    ) -> dict:
        factor = _build_factor(FactorSpec(name=name, lookback=lookback, item=item))
        with lock:
            dates = sample_as_of_dates(store, _parse(start), _parse(end), step=step)
            as_of_pool = store.get_universe(
                universe_index, _parse(end), approximate_from_latest=True
            )
            summary = evaluate_factor_series(factor, store, as_of_pool, dates, horizon=horizon)
        stats = summary.rank_ic
        return {
            "factor": factor.name,
            "rank_ic": {
                "mean": stats.mean,
                "ir": stats.ir,
                "positive_rate": stats.positive_rate,
                "n": stats.n,
            },
        }

    @app.get("/api/instrument")
    def instrument(code: str) -> dict:
        """单标的（ETF）描述性研究：价格坐标（回撤/趋势/波动/收益分布）。

        实时从新浪拉 ETF 日线并计算。**返回的是历史坐标，不是买卖信号。**
        """

        prov = provider
        if prov is None:
            import importlib

            prov = importlib.import_module("akshare")
        try:
            series = fetch_etf_bars_sina(code, prov)
        except EtfSourceError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:  # noqa: BLE001 - 代码非法/网络失败统一回 400
            raise HTTPException(status_code=400, detail=f"取 {code} 失败：{error}") from error

        result = describe_prices([d for d, _ in series], [c for _, c in series])
        result["code"] = code
        result["note"] = "历史坐标，非买卖信号；不预测未来。"

        # 自带估值（若已上传）：算"贵/便宜"分位。优先 pe_ttm。
        result["valuation"] = None
        with lock:
            items = store.instrument_valuation_items(code)
            if items:
                item = "pe_ttm" if "pe_ttm" in items else items[0]
                val_series = store.get_instrument_valuation(code, item)
                vp = valuation_percentile([v for _, v in val_series])
                vp["item"] = item
                vp["start"] = str(val_series[0][0])
                vp["end"] = str(val_series[-1][0])
                result["valuation"] = vp
        return result

    @app.post("/api/instrument/valuation")
    def upload_valuation(body: ValuationUpload) -> dict:
        """自带估值数据的通道：上传某标的的估值序列（如恒生科技 PE）。"""

        points = [(_parse(p.date), p.value) for p in body.points]
        with lock:
            store.write_instrument_valuation(body.code, body.item, points, body.source)
        return {"code": body.code, "item": body.item, "written": len(points)}

    return app
