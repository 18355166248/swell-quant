from __future__ import annotations

import argparse

import uvicorn

from swell_quant.api.server import create_app
from swell_quant.marketdata.store import MarketStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Swell Quant 研究看板后端桥")
    parser.add_argument("--db", required=True, help="DuckDB 库路径")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    store = MarketStore(args.db)
    app = create_app(store)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
