import json
from pathlib import Path

from swell_quant.data.source_status import (
    build_data_source_status,
    build_data_source_status_from_metadata,
    default_data_source_metadata_path,
)


def test_default_data_source_metadata_path_points_to_raw_metadata() -> None:
    assert default_data_source_metadata_path(Path("data")) == Path("data/raw/data_source.json")


def test_data_source_status_passes_for_complete_sample_metadata() -> None:
    status = build_data_source_status_from_metadata(
        {
            "data_source": "sample",
            "market": "A_SHARE_DAILY",
            "universe_mode": "sample",
            "universe_name": "本地样例 A 股股票池",
            "benchmark": "CSI800",
            "benchmark_name": "中证 800",
            "selected_symbol_count": 3,
            "resolved_symbol_count": 3,
            "succeeded_symbol_count": 3,
            "failed_symbol_count": 0,
            "failed_symbols": [],
            "updated_at": "2024-01-01T00:00:00Z",
        }
    )

    assert status["status"] == "passed"
    assert status["passed"] is True
    assert status["warning_count"] == 0
    assert status["failed_count"] == 0
    assert status["disclaimer"] == "仅用于研究，不构成投资建议"


def test_data_source_status_warns_for_partial_akshare_trial() -> None:
    status = build_data_source_status_from_metadata(
        {
            "data_source": "akshare",
            "market": "A_SHARE_DAILY",
            "universe_mode": "csi800",
            "selected_symbol_count": 20,
            "resolved_symbol_count": 800,
            "succeeded_symbol_count": 19,
            "failed_symbol_count": 1,
            "max_symbols": 20,
            "failed_symbols": [{"symbol": "000001.SZ", "reason": "timeout"}],
        }
    )

    assert status["status"] == "warning"
    assert status["passed"] is True
    assert status["warning_count"] == 2
    assert status["failed_symbol_count"] == 1
    assert status["failed_symbols"][0]["symbol"] == "000001.SZ"


def test_data_source_status_fails_when_metadata_is_missing(tmp_path: Path) -> None:
    status = build_data_source_status(tmp_path / "missing.json")

    assert status["status"] == "missing"
    assert status["passed"] is False
    assert status["failed_count"] == 1


def test_data_source_status_reads_metadata_file(tmp_path: Path) -> None:
    metadata_path = tmp_path / "data_source.json"
    metadata_path.write_text(
        json.dumps(
            {
                "data_source": "sample",
                "selected_symbol_count": 3,
                "succeeded_symbol_count": 3,
                "failed_symbol_count": 0,
            }
        ),
        encoding="utf-8",
    )

    status = build_data_source_status(metadata_path)

    assert status["status"] == "passed"
    assert status["path"] == str(metadata_path)
