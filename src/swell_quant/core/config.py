from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SUPPORTED_DATA_SOURCES = {"sample", "akshare"}
SUPPORTED_AKSHARE_UNIVERSE_MODES = {"manual"}
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
                "AKSHARE_UNIVERSE_MODE currently supports only 'manual'; "
                "真实沪深300+中证500成分股自动拉取会在后续数据源阶段接入"
            )
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


def _parse_symbol_list(value: str) -> tuple[str, ...]:
    symbols = tuple(symbol.strip() for symbol in value.split(",") if symbol.strip())
    if not symbols:
        raise ValueError("AKSHARE_SYMBOLS must include at least one symbol")
    return symbols


def _parse_akshare_date(value: str, name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{name} must use YYYYMMDD format") from error
