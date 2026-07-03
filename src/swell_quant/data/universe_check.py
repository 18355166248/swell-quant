from __future__ import annotations

from typing import Any

from swell_quant.core.config import Settings
from swell_quant.data.akshare_data import resolve_akshare_symbols

MIN_CSI800_SYMBOL_COUNT = 700


def build_akshare_universe_payload(
    settings: Settings,
    provider: Any | None = None,
) -> dict[str, Any]:
    symbols = resolve_akshare_symbols(
        universe_mode=settings.akshare_universe_mode,
        manual_symbols=settings.akshare_symbols,
        provider=provider,
    )
    status = _resolve_universe_status(settings.akshare_universe_mode, len(symbols))
    return {
        # 该检查只验证股票池解析，不拉行情；真实 pipeline 前先用它降低 AKShare 接口和股票池配置风险。
        "status": status,
        "passed": status == "passed",
        "data_source": settings.data_source,
        "universe_mode": settings.akshare_universe_mode,
        "symbol_count": len(symbols),
        "minimum_expected_count": _minimum_expected_count(settings.akshare_universe_mode),
        "symbols_sample": list(symbols[:10]),
        "disclaimer": "仅用于研究，不构成投资建议",
    }


def _resolve_universe_status(universe_mode: str, symbol_count: int) -> str:
    minimum_expected_count = _minimum_expected_count(universe_mode)
    if symbol_count < minimum_expected_count:
        return "failed"
    return "passed"


def _minimum_expected_count(universe_mode: str) -> int:
    return MIN_CSI800_SYMBOL_COUNT if universe_mode in {"csi800", "hs300_csi500"} else 1
