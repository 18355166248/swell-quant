from swell_quant.core.config import Settings


def test_settings_loads_akshare_data_source(monkeypatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "akshare")
    monkeypatch.setenv("AKSHARE_SYMBOLS", "000001.SZ, 600000.SH")
    monkeypatch.setenv("AKSHARE_START_DATE", "20240102")
    monkeypatch.setenv("AKSHARE_END_DATE", "20240201")
    monkeypatch.setenv("AKSHARE_BENCHMARK_SYMBOL", "sh000906")

    settings = Settings.from_env()

    assert settings.data_source == "akshare"
    assert settings.akshare_symbols == ("000001.SZ", "600000.SH")
    assert settings.akshare_start_date == "20240102"
    assert settings.akshare_end_date == "20240201"
    assert settings.akshare_benchmark_symbol == "sh000906"
