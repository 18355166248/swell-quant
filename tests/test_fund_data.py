from __future__ import annotations

from datetime import date

from swell_quant.data.fund_data import collect_akshare_fund_data


class FakeFrame:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def to_dict(self, orient: str) -> list[dict]:
        assert orient == "records"
        return self.rows


class FakeFundProvider:
    def __init__(self) -> None:
        self.open_calls: list[str] = []

    def fund_name_em(self) -> FakeFrame:
        return FakeFrame(
            [
                {"基金代码": "510300", "基金简称": "沪深300ETF", "基金类型": "指数型"},
                {"基金代码": "159915", "基金简称": "创业板ETF", "基金类型": "指数型"},
            ]
        )

    def fund_open_fund_info_em(self, *, symbol: str, indicator: str, period: str) -> FakeFrame:
        assert indicator == "单位净值走势"
        assert period == "成立来"
        self.open_calls.append(symbol)
        if symbol == "159915":
            raise RuntimeError("open endpoint unavailable")
        return FakeFrame(
            [
                {"净值日期": "2025-01-01", "单位净值": 0.99},
                {"净值日期": "2025-01-02", "单位净值": 1.0},
                {"净值日期": "2025-01-03", "单位净值": 1.02},
            ]
        )

    def fund_etf_fund_info_em(self, *, fund: str, start_date: str, end_date: str) -> FakeFrame:
        assert fund == "159915"
        assert start_date == "20250102"
        assert end_date == "20250103"
        return FakeFrame(
            [
                {"日期": "2025-01-02", "单位净值": 2.0},
                {"日期": "2025-01-03", "单位净值": 2.04},
            ]
        )


def test_collect_akshare_fund_data_parses_names_and_navs() -> None:
    provider = FakeFundProvider()

    result = collect_akshare_fund_data(
        fund_codes=("510300", "159915"),
        start_date="20250102",
        end_date="20250103",
        provider=provider,
    )

    assert result.succeeded_codes == ("510300", "159915")
    assert result.failed_codes == ()
    assert [fund.fund_name for fund in result.funds] == ["沪深300ETF", "创业板ETF"]
    assert result.funds[0].inception_date == date(2025, 1, 2)
    assert [nav.nav for nav in result.navs if nav.fund_code == "510300"] == [1.0, 1.02]
    assert [attempt.source for attempt in result.attempts] == [
        "fund_open_fund_info_em",
        "fund_etf_fund_info_em",
    ]
    assert result.metadata["succeeded_count"] == 2
