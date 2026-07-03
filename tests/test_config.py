from pathlib import Path

import pytest

from swell_quant.core.config import Settings, build_settings_preflight


def test_env_example_documents_all_supported_environment_variables() -> None:
    expected_variables = {
        "DATA_DIR",
        "DUCKDB_PATH",
        "DATA_SOURCE",
        "AKSHARE_UNIVERSE_MODE",
        "AKSHARE_SYMBOLS",
        "AKSHARE_START_DATE",
        "AKSHARE_END_DATE",
        "AKSHARE_BENCHMARK_SYMBOL",
        "AKSHARE_MAX_SYMBOLS",
        "MODEL_TYPE",
        "LLM_PROVIDER",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
    }
    documented_variables = {
        line.split("=", 1)[0]
        for line in Path(".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }

    assert expected_variables <= documented_variables


def test_settings_loads_akshare_data_source(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "akshare")
    monkeypatch.setenv("AKSHARE_UNIVERSE_MODE", "manual")
    monkeypatch.setenv("AKSHARE_SYMBOLS", "000001.SZ, 600000.SH")
    monkeypatch.setenv("AKSHARE_START_DATE", "20240102")
    monkeypatch.setenv("AKSHARE_END_DATE", "20240201")
    monkeypatch.setenv("AKSHARE_BENCHMARK_SYMBOL", "sh000906")
    monkeypatch.setenv("AKSHARE_MAX_SYMBOLS", "20")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    settings = Settings.from_env()

    assert settings.data_source == "akshare"
    assert settings.akshare_universe_mode == "manual"
    assert settings.akshare_symbols == ("000001.SZ", "600000.SH")
    assert settings.akshare_start_date == "20240102"
    assert settings.akshare_end_date == "20240201"
    assert settings.akshare_benchmark_symbol == "sh000906"
    assert settings.akshare_max_symbols == 20
    assert settings.llm_provider == "deepseek"
    assert settings.deepseek_model == "deepseek-chat"


def test_settings_allows_csi800_universe_without_manual_symbols(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "akshare")
    monkeypatch.setenv("AKSHARE_UNIVERSE_MODE", "csi800")
    monkeypatch.setenv("AKSHARE_SYMBOLS", "")

    settings = Settings.from_env()

    assert settings.akshare_universe_mode == "csi800"
    assert settings.akshare_symbols == ()


def test_settings_preflight_accepts_runtime_resolved_csi800_symbols() -> None:
    settings = Settings(
        data_dir=Path("./data"),
        duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
        data_source="akshare",
        akshare_universe_mode="csi800",
        akshare_symbols=(),
    )

    preflight = build_settings_preflight(settings)

    assert preflight["status"] == "passed"
    assert preflight["failed_count"] == 0
    assert any(
        check["key"] == "akshare_symbols"
        and check["status"] == "passed"
        and "运行时" in check["message"]
        for check in preflight["checks"]
    )


def test_settings_preflight_warns_for_akshare_max_symbols() -> None:
    settings = Settings(
        data_dir=Path("./data"),
        duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
        data_source="akshare",
        akshare_universe_mode="csi800",
        akshare_symbols=(),
        akshare_max_symbols=20,
    )

    preflight = build_settings_preflight(settings)

    assert preflight["status"] == "warning"
    assert any(
        check["key"] == "akshare_max_symbols"
        and check["status"] == "warning"
        and "20" in check["message"]
        for check in preflight["checks"]
    )


def test_settings_allows_hs300_csi500_universe_alias() -> None:
    settings = Settings(
        data_dir=Path("./data"),
        duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
        akshare_universe_mode="hs300_csi500",
        akshare_symbols=(),
    )

    assert settings.akshare_universe_mode == "hs300_csi500"
    assert settings.akshare_symbols == ()


def test_settings_rejects_empty_manual_akshare_symbols() -> None:
    with pytest.raises(ValueError, match="manual mode"):
        Settings(
            data_dir=Path("./data"),
            duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
            akshare_universe_mode="manual",
            akshare_symbols=(),
        )


def test_settings_rejects_invalid_akshare_symbol() -> None:
    with pytest.raises(ValueError, match="AKSHARE_SYMBOLS"):
        Settings(
            data_dir=Path("./data"),
            duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
            akshare_symbols=("000001",),
        )


def test_settings_rejects_unsupported_akshare_universe_mode() -> None:
    with pytest.raises(ValueError, match="AKSHARE_UNIVERSE_MODE"):
        Settings(
            data_dir=Path("./data"),
            duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
            akshare_universe_mode="all_a",
        )


def test_settings_rejects_invalid_akshare_date_range() -> None:
    with pytest.raises(ValueError, match="AKSHARE_START_DATE"):
        Settings(
            data_dir=Path("./data"),
            duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
            akshare_start_date="20240301",
            akshare_end_date="20240201",
        )


def test_settings_rejects_invalid_akshare_max_symbols(monkeypatch) -> None:
    monkeypatch.setenv("AKSHARE_MAX_SYMBOLS", "0")

    with pytest.raises(ValueError, match="AKSHARE_MAX_SYMBOLS"):
        Settings.from_env()
