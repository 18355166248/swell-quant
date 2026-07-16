from __future__ import annotations

import threading
from datetime import date, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from swell_quant.analysis import describe_prices, valuation_percentile
from swell_quant.marketdata.source_etf import EtfSourceError, fetch_etf_bars_sina
from swell_quant.marketdata.source_index_valuation import (
    IndexValuationSourceError,
    fetch_index_valuation_danjuan,
)
from swell_quant.marketdata.store import MarketStore
from swell_quant.service import FACTOR_CATALOG, run_backtest, run_factor_ic


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


class ValuationRefresh(BaseModel):
    code: str  # 标的代码，如 "513260"
    danjuan_index: str  # 蛋卷指数代码，如 "HKHSTECH"
    item: str = "pe_ttm"


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


def _parse(day: str) -> date:
    return datetime.strptime(day, "%Y-%m-%d").date()


def create_app(
    store: MarketStore,
    provider: object | None = None,
    valuation_fetch=fetch_index_valuation_danjuan,
) -> FastAPI:
    """构建 FastAPI 应用。``store`` 为已打开的 MarketStore（测试传内存库）。

    ``provider`` 为行情提供者（真实为 akshare，用于 ETF 实时研究；为 None 时按需
    懒加载 akshare）。``valuation_fetch`` 为指数估值拉取器（默认蛋卷，测试可注入）。
    DuckDB 连接非线程安全，用锁串行化——个人单用户看板足够。
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
        with lock:
            try:
                return run_backtest(
                    store,
                    factors=[s.model_dump() for s in req.factors],
                    start=_parse(req.start),
                    end=_parse(req.end),
                    step=req.step,
                    horizon=req.horizon,
                    top_n=req.top_n,
                    cost_bps=req.cost_bps,
                    benchmark=req.benchmark,
                    benchmark_index=req.benchmark_index,
                    universe_index=req.universe_index,
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

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
        with lock:
            try:
                return run_factor_ic(
                    store,
                    name=name,
                    start=_parse(start),
                    end=_parse(end),
                    lookback=lookback,
                    item=item,
                    step=step,
                    horizon=horizon,
                    universe_index=universe_index,
                )
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

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

    @app.post("/api/instrument/valuation/refresh")
    def refresh_valuation(body: ValuationRefresh) -> dict:
        """一键更新：从蛋卷估值中心拉指数 PE 全量历史，落库到该标的。"""

        try:
            series = valuation_fetch(body.danjuan_index)
        except IndexValuationSourceError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except Exception as error:  # noqa: BLE001 - 网络/解析失败统一回 502
            raise HTTPException(status_code=502, detail=f"拉取估值失败：{error}") from error

        with lock:
            store.write_instrument_valuation(
                body.code, body.item, series, f"danjuan:{body.danjuan_index}"
            )
        percentile = valuation_percentile([v for _, v in series])
        return {
            "code": body.code,
            "item": body.item,
            "written": len(series),
            "current": percentile["current"],
            "percentile": percentile["percentile"],
        }

    return app
