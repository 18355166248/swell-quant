from pathlib import Path

from swell_quant.research.funds import (
    build_fund_candidates,
    build_fund_verification,
    compute_fund_metrics,
    generate_sample_funds,
    read_fund_candidates_csv,
    read_fund_metrics_csv,
    write_fund_candidates_csv,
    write_fund_metrics_csv,
    write_fund_nav_csv,
    write_funds_csv,
)


def test_compute_fund_metrics_reports_returns_risk_and_costs() -> None:
    funds, navs = generate_sample_funds()

    metrics = compute_fund_metrics(funds, navs)

    assert len(metrics) == len(funds)
    first = metrics[0]
    assert first.return_1y != 0
    assert first.max_drawdown <= 0
    assert first.volatility >= 0
    assert first.downside_volatility >= 0
    assert first.total_fee == first.management_fee + first.custody_fee
    assert first.age_years > 0


def test_build_fund_candidates_sorts_by_profile_score() -> None:
    funds, navs = generate_sample_funds()
    metrics = compute_fund_metrics(funds, navs)

    conservative = build_fund_candidates(metrics, profile="conservative")
    aggressive = build_fund_candidates(metrics, profile="aggressive")

    assert conservative[0].rank == 1
    assert aggressive[0].rank == 1
    assert conservative[0].profile == "conservative"
    assert aggressive[0].profile == "aggressive"
    assert conservative[0].factor_reasons
    assert conservative[0].score_level in {"high", "medium", "low"}
    assert conservative[0].verification_status in {"ready", "review", "block"}
    assert conservative[0].verification_label
    assert conservative[0].verification_checks
    assert "当前为样例基金数据" in conservative[0].verification_blockers[0]


def test_build_fund_verification_accepts_api_metric_dict() -> None:
    funds, navs = generate_sample_funds()
    metric = compute_fund_metrics(funds, navs)[0]
    verification = build_fund_verification(
        {
            "age_years": metric.age_years,
            "max_drawdown": metric.max_drawdown,
            "volatility": metric.volatility,
            "total_fee": metric.total_fee,
            "aum_billion": metric.aum_billion,
        }
    )

    assert verification["status"] == "block"
    assert verification["checks"]
    assert verification["blockers"]


def test_fund_csv_roundtrip(tmp_path: Path) -> None:
    funds, navs = generate_sample_funds()
    metrics = compute_fund_metrics(funds, navs)
    candidates = build_fund_candidates(metrics, profile="balanced")

    write_funds_csv(tmp_path / "sample_funds.csv", funds)
    write_fund_nav_csv(tmp_path / "sample_fund_nav.csv", navs)
    write_fund_metrics_csv(tmp_path / "sample_fund_metrics.csv", metrics)
    write_fund_candidates_csv(tmp_path / "sample_fund_candidates_balanced.csv", candidates)

    parsed_metrics = read_fund_metrics_csv(tmp_path / "sample_fund_metrics.csv")
    parsed_candidates = read_fund_candidates_csv(tmp_path / "sample_fund_candidates_balanced.csv")

    assert parsed_metrics[0]["fund_code"] == funds[0].fund_code
    assert parsed_candidates[0]["profile"] == "balanced"
    assert parsed_candidates[0]["verification_status"] in {"ready", "review", "block"}
    assert parsed_candidates[0]["verification_checks"]
    assert parsed_candidates[0]["verification_blockers"]
