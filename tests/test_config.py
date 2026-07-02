from pathlib import Path

import pytest

from swell_quant.core.config import Settings


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
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    settings = Settings.from_env()

    assert settings.data_source == "akshare"
    assert settings.akshare_universe_mode == "manual"
    assert settings.akshare_symbols == ("000001.SZ", "600000.SH")
    assert settings.akshare_start_date == "20240102"
    assert settings.akshare_end_date == "20240201"
    assert settings.akshare_benchmark_symbol == "sh000906"
    assert settings.llm_provider == "deepseek"
    assert settings.deepseek_model == "deepseek-chat"


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
            akshare_universe_mode="target_csi800",
        )


def test_settings_rejects_invalid_akshare_date_range() -> None:
    with pytest.raises(ValueError, match="AKSHARE_START_DATE"):
        Settings(
            data_dir=Path("./data"),
            duckdb_path=Path("./data/duckdb/swell_quant.duckdb"),
            akshare_start_date="20240301",
            akshare_end_date="20240201",
        )
