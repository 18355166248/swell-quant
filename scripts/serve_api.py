#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from swell_quant.api.local_server import create_server
from swell_quant.core.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Swell Quant local read-only API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    settings = Settings.from_env()
    server = create_server(args.host, args.port, settings.data_dir, settings=settings)
    print(f"serving read-only API on http://{args.host}:{args.port}")
    print("available endpoints: /api/health /api/status /api/settings /api/tasks /api/predictions /api/backtests /api/pipeline /api/report")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
