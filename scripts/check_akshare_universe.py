#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.core.config import Settings
from swell_quant.data.akshare_data import AkshareDependencyError, resolve_akshare_symbols


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AKShare universe resolution.")
    parser.add_argument("--json", action="store_true", help="print structured JSON")
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
        payload = build_akshare_universe_payload(settings)
    except ValueError as error:
        payload = {
            "status": "failed",
            "passed": False,
            "error": "invalid_settings",
            "message": str(error),
        }
        return _emit(payload, as_json=args.json, exit_code=2)
    except (AkshareDependencyError, AttributeError) as error:
        payload = {
            "status": "failed",
            "passed": False,
            "error": "akshare_universe_unavailable",
            "message": str(error),
        }
        return _emit(payload, as_json=args.json, exit_code=1)

    return _emit(payload, as_json=args.json, exit_code=0 if payload["passed"] else 1)


def _resolve_universe_status(universe_mode: str, symbol_count: int) -> str:
    minimum_expected_count = _minimum_expected_count(universe_mode)
    if symbol_count < minimum_expected_count:
        return "failed"
    return "passed"


def _minimum_expected_count(universe_mode: str) -> int:
    return MIN_CSI800_SYMBOL_COUNT if universe_mode in {"csi800", "hs300_csi500"} else 1


def _emit(payload: dict[str, Any], *, as_json: bool, exit_code: int) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"akshare_universe_status={payload['status']}")
        print(f"passed={str(payload['passed']).lower()}")
        if "error" in payload:
            print(f"error={payload['error']}")
            print(f"message={payload['message']}")
        else:
            print(f"data_source={payload['data_source']}")
            print(f"universe_mode={payload['universe_mode']}")
            print(f"symbol_count={payload['symbol_count']}")
            print(f"minimum_expected_count={payload['minimum_expected_count']}")
            print(f"symbols_sample={','.join(payload['symbols_sample'])}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
