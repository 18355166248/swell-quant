from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    duckdb_path: Path
    deepseek_api_key: str | None = None
    openai_api_key: str | None = None
    model_type: str = "lightgbm"
    data_source: str = "sample"
    akshare_symbols: tuple[str, ...] = ("000001.SZ", "000002.SZ", "600000.SH")
    akshare_start_date: str = "20240101"
    akshare_end_date: str = "20240229"
    akshare_benchmark_symbol: str = "sh000906"

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
            data_source=os.getenv("DATA_SOURCE", "sample"),
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


def _parse_symbol_list(value: str) -> tuple[str, ...]:
    symbols = tuple(symbol.strip() for symbol in value.split(",") if symbol.strip())
    if not symbols:
        raise ValueError("AKSHARE_SYMBOLS must include at least one symbol")
    return symbols
