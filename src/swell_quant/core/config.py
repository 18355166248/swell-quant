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
        )

    def ensure_directories(self) -> None:
        # 数据和产物目录是研究链路的根，统一在配置层创建，避免各阶段各自散落处理路径。
        for subdir in ("raw", "processed", "duckdb", "models", "reports"):
            (self.data_dir / subdir).mkdir(parents=True, exist_ok=True)
