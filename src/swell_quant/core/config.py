from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SUPPORTED_DATA_SOURCES = {"sample", "akshare"}
SUPPORTED_AKSHARE_UNIVERSE_MODES = {"manual", "csi800", "hs300_csi500"}
_A_SHARE_SYMBOL_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    duckdb_path: Path
    deepseek_api_key: str | None = None
    openai_api_key: str | None = None
    model_type: str = "lightgbm"
    llm_provider: str = "disabled"
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/chat/completions"
    data_source: str = "sample"
    akshare_universe_mode: str = "manual"
    akshare_symbols: tuple[str, ...] = ("000001.SZ", "000002.SZ", "600000.SH")
    akshare_start_date: str = "20240101"
    akshare_end_date: str = "20240229"
    akshare_benchmark_symbol: str = "sh000906"

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_source", self.data_source.strip().lower())
        object.__setattr__(
            self,
            "akshare_universe_mode",
            self.akshare_universe_mode.strip().lower(),
        )
        object.__setattr__(
            self,
            "akshare_symbols",
            tuple(symbol.strip().upper() for symbol in self.akshare_symbols if symbol.strip()),
        )
        self.validate()

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("DATA_DIR", "./data")).expanduser()
        duckdb_path = Path(
            os.getenv("DUCKDB_PATH", str(data_dir / "duckdb" / "swell_quant.duckdb"))
        ).expanduser()
        return cls(
            data_dir=data_dir,
            duckdb_path=duckdb_path,
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            model_type=os.getenv("MODEL_TYPE", "lightgbm"),
            llm_provider=os.getenv("LLM_PROVIDER", "disabled"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions"
            ),
            data_source=os.getenv("DATA_SOURCE", "sample"),
            akshare_universe_mode=os.getenv("AKSHARE_UNIVERSE_MODE", "manual"),
            akshare_symbols=_parse_symbol_list(
                os.getenv("AKSHARE_SYMBOLS", "000001.SZ,000002.SZ,600000.SH")
            ),
            akshare_start_date=os.getenv("AKSHARE_START_DATE", "20240101"),
            akshare_end_date=os.getenv("AKSHARE_END_DATE", "20240229"),
            akshare_benchmark_symbol=os.getenv("AKSHARE_BENCHMARK_SYMBOL", "sh000906"),
        )

    def ensure_directories(self) -> None:
        # 数据和产物目录是研究链路的根，统一在配置层创建，避免各阶段各自散落处理路径。
        for subdir in ("raw", "processed", "duckdb", "models", "reports"):
            (self.data_dir / subdir).mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        # 配置校验放在 Settings 层，确保 CLI、API 和页面触发 pipeline 时使用同一套数据源前置门禁。
        if self.data_source not in SUPPORTED_DATA_SOURCES:
            raise ValueError(
                f"DATA_SOURCE must be one of {sorted(SUPPORTED_DATA_SOURCES)}, "
                f"got {self.data_source!r}"
            )
        if self.akshare_universe_mode not in SUPPORTED_AKSHARE_UNIVERSE_MODES:
            raise ValueError(
                f"AKSHARE_UNIVERSE_MODE must be one of {sorted(SUPPORTED_AKSHARE_UNIVERSE_MODES)}"
            )
        if self.akshare_universe_mode == "manual" and not self.akshare_symbols:
            raise ValueError("AKSHARE_SYMBOLS must include at least one symbol in manual mode")
        invalid_symbols = [
            symbol for symbol in self.akshare_symbols if not _A_SHARE_SYMBOL_PATTERN.match(symbol)
        ]
        if invalid_symbols:
            raise ValueError(
                "AKSHARE_SYMBOLS must use 6-digit A-share symbols with .SH/.SZ/.BJ suffix; "
                f"invalid={invalid_symbols}"
            )
        start = _parse_akshare_date(self.akshare_start_date, "AKSHARE_START_DATE")
        end = _parse_akshare_date(self.akshare_end_date, "AKSHARE_END_DATE")
        if start > end:
            raise ValueError("AKSHARE_START_DATE must be earlier than or equal to AKSHARE_END_DATE")


def build_settings_preflight(settings: Settings) -> dict[str, object]:
    checks: list[dict[str, str]] = [
        {
            "key": "data_source",
            "name": "数据源",
            "status": "passed",
            "message": f"当前使用 {settings.data_source}",
        },
        {
            "key": "akshare_universe_mode",
            "name": "AKShare 股票池模式",
            "status": "passed",
            "message": f"当前使用 {settings.akshare_universe_mode} 股票池模式",
        },
        {
            "key": "akshare_symbols",
            "name": "AKShare 股票池",
            "status": "passed"
            if settings.akshare_universe_mode != "manual" or settings.akshare_symbols
            else "failed",
            "message": _akshare_symbols_preflight_message(settings),
        },
        {
            "key": "akshare_date_range",
            "name": "AKShare 日期区间",
            "status": "passed",
            "message": f"{settings.akshare_start_date} 至 {settings.akshare_end_date}",
        },
        {
            "key": "duckdb_path",
            "name": "DuckDB 路径",
            "status": "passed",
            "message": str(settings.duckdb_path),
        },
    ]
    if (
        settings.data_source == "akshare"
        and settings.akshare_universe_mode == "manual"
        and len(settings.akshare_symbols) < 10
    ):
        checks.append(
            {
                "key": "akshare_symbol_count",
                "name": "AKShare 标的数量",
                "status": "warning",
                "message": "当前手工股票池小于 10 只，只适合连通性验证，不适合评估策略稳定性",
            }
        )
    if settings.llm_provider == "deepseek" and settings.deepseek_api_key is None:
        checks.append(
            {
                "key": "deepseek_api_key",
                "name": "DeepSeek Key",
                "status": "warning",
                "message": "LLM_PROVIDER=deepseek 但未配置 DEEPSEEK_API_KEY，AI 报告会跳过生成",
            }
        )
    failed_count = sum(1 for check in checks if check["status"] == "failed")
    warning_count = sum(1 for check in checks if check["status"] == "warning")
    return {
        # 预检面向 CLI、API 和页面消费；Settings 已拦截非法配置，这里补充运行前可读的风险提示。
        "status": "failed" if failed_count else "warning" if warning_count else "passed",
        "passed": failed_count == 0,
        "check_count": len(checks),
        "failed_count": failed_count,
        "warning_count": warning_count,
        "checks": checks,
    }


def _parse_symbol_list(value: str) -> tuple[str, ...]:
    symbols = tuple(symbol.strip() for symbol in value.split(",") if symbol.strip())
    return symbols


def _akshare_symbols_preflight_message(settings: Settings) -> str:
    if settings.akshare_universe_mode == "manual":
        return f"已配置 {len(settings.akshare_symbols)} 个手工标的"
    return "运行时将从 AKShare 拉取沪深 300 + 中证 500 成分股"


def _parse_akshare_date(value: str, name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{name} must use YYYYMMDD format") from error
