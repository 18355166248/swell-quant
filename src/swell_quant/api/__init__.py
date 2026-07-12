"""api: 只读的 FastAPI 桥，把 marketdata/factors/portfolio 暴露给研究看板。

不承载业务逻辑，只做“取参数 → 调库 → 返回 JSON”。运行：
    python -m swell_quant.api --db data/duckdb/marketdata.duckdb
"""

from swell_quant.api.server import create_app

__all__ = ["create_app"]
