from pathlib import Path
from types import SimpleNamespace

import pytest

import swell_quant.research.modeling as modeling
from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.features import compute_features, read_features_csv, write_features_csv
from swell_quant.research.labels import compute_labels
from swell_quant.research.modeling import (
    BASELINE_MODEL_VERSION,
    LIGHTGBM_MODEL_VERSION,
    build_rank_signal_metrics,
    build_training_samples,
    build_walk_forward_folds,
    build_walk_forward_metrics,
    generate_historical_predictions,
    generate_predictions,
    read_training_samples_csv,
    train_baseline_model,
    train_model,
    write_training_samples_csv,
)


class FakeDataset:
    def __init__(
        self,
        rows: list[list[float]],
        label: list[int],
        feature_name: list[str],
    ) -> None:
        self.rows = rows
        self.label = label
        self.feature_name = feature_name


class FakeBooster:
    def __init__(self) -> None:
        self.saved_path: str | None = None

    def predict(self, rows: list[list[float]]) -> list[float]:
        return [sum(value for value in row if value == value) for row in rows]

    def save_model(self, path: str) -> None:
        self.saved_path = path
        Path(path).write_text("fake lightgbm model\n", encoding="utf-8")

    def feature_importance(self, importance_type: str) -> list[float]:
        if importance_type == "gain":
            return [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        return [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]


def test_baseline_model_metadata_uses_labeled_rows() -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)

    metadata = train_baseline_model(features, labels)

    assert metadata.model_version == BASELINE_MODEL_VERSION
    assert metadata.model_type == "rule_baseline"
    assert metadata.requested_model_type == "lightgbm"
    assert metadata.training_backend == "rule_baseline_fallback"
    assert metadata.dependency_status in {"lightgbm_available", "lightgbm_missing"}
    assert metadata.training_params is not None
    assert metadata.training_params["requires_fit"] is False
    assert metadata.feature_importance is not None
    assert metadata.feature_importance[0]["feature_name"] == "momentum_5d"
    assert metadata.feature_importance[0]["importance_type"] == "rule_weight"
    assert metadata.feature_names == [
        "momentum_5d",
        "return_1d",
        "volatility_5d",
        "rsi_6",
        "macd_hist",
        "volume_change_1d",
    ]
    assert metadata.train_start == "2024-01-02"
    assert metadata.train_end == "2024-01-16"
    assert metadata.prediction_date == "2024-01-21"
    assert metadata.label_gap_days == 5
    assert metadata.evaluation_status == "ready"
    assert metadata.evaluation_train_start == "2024-01-02"
    assert metadata.evaluation_train_end == "2024-01-04"
    assert metadata.validation_start == "2024-01-10"
    assert metadata.validation_end == "2024-01-10"
    assert metadata.test_start == "2024-01-16"
    assert metadata.test_end == "2024-01-16"
    assert metadata.metrics is not None
    assert metadata.metrics["labeled_row_count"] == 45
    assert metadata.metrics["test_prediction_dates"] == 1
    assert metadata.disclaimer == "仅用于研究，不构成投资建议"


def test_generate_predictions_ranks_latest_date_only() -> None:
    features = compute_features(generate_sample_bars(days=20))
    predictions = generate_predictions(features)

    assert len(predictions) == 3
    assert {row.trade_date.isoformat() for row in predictions} == {"2024-01-21"}
    assert [row.rank for row in predictions] == [1, 2, 3]
    assert predictions[0].score >= predictions[1].score >= predictions[2].score


def test_train_model_dispatches_requested_backend() -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)

    default_metadata = train_model(features, labels)
    baseline_metadata = train_model(features, labels, requested_model_type="rule_baseline")

    assert default_metadata.requested_model_type == "lightgbm"
    assert default_metadata.training_backend == "rule_baseline_fallback"
    assert baseline_metadata.requested_model_type == "rule_baseline"
    assert baseline_metadata.training_backend == "rule_baseline"
    assert baseline_metadata.dependency_status == "not_required"


def test_train_model_uses_lightgbm_when_dependency_is_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    booster = FakeBooster()
    fake_lightgbm = SimpleNamespace(
        Dataset=FakeDataset,
        train=lambda params, train_set, num_boost_round: booster,
    )
    monkeypatch.setattr(modeling, "is_lightgbm_available", lambda: True)
    monkeypatch.setattr(modeling, "_load_lightgbm_module", lambda: fake_lightgbm)
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)
    model_path = tmp_path / "lightgbm-v1.txt"

    metadata = train_model(features, labels, model_output_path=model_path)
    predictions = generate_predictions(features, metadata.model_version, metadata, booster)

    assert metadata.model_version == LIGHTGBM_MODEL_VERSION
    assert metadata.model_type == "lightgbm"
    assert metadata.training_backend == "lightgbm"
    assert metadata.dependency_status == "lightgbm_available"
    assert metadata.training_params is not None
    assert metadata.training_params["objective"] == "binary"
    assert metadata.model_artifact_path == str(model_path)
    assert metadata.feature_importance is not None
    assert metadata.feature_importance[0]["feature_name"] == "momentum_5d"
    assert metadata.feature_importance[0]["importance_type"] == "lightgbm_gain"
    assert metadata.feature_importance[0]["split_count"] == 6
    assert model_path.exists()
    assert predictions[0].model_version == LIGHTGBM_MODEL_VERSION
    assert predictions[0].score >= predictions[-1].score


def test_train_model_rejects_unsupported_backend() -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)

    with pytest.raises(ValueError, match="unsupported model type"):
        train_model(features, labels, requested_model_type="deep_model")


def test_build_training_samples_preserves_time_split_and_missing_features(tmp_path: Path) -> None:
    bars = generate_sample_bars(days=20)
    rows = build_training_samples(compute_features(bars), compute_labels(bars))
    path = write_training_samples_csv(tmp_path / "training_samples.csv", rows)
    loaded = read_training_samples_csv(path)

    assert len(rows) == 45
    assert {row.split for row in rows} == {"train", "validation", "test", "gap"}
    assert sum(1 for row in rows if row.split == "train") == 9
    assert sum(1 for row in rows if row.split == "validation") == 3
    assert sum(1 for row in rows if row.split == "test") == 3
    assert rows[0].return_1d is None
    assert rows[0].macd_hist == 0.0
    assert len(loaded) == len(rows)
    assert loaded[0].split == "train"
    assert loaded[0].return_1d is None


def test_generate_historical_predictions_skips_rows_without_lookback() -> None:
    features = compute_features(generate_sample_bars(days=7))
    predictions = generate_historical_predictions(features)

    assert {row.trade_date.isoformat() for row in predictions} == {"2024-01-07", "2024-01-08"}
    assert len(predictions) == 6


def test_rank_signal_metrics_reward_correct_ordering() -> None:
    from datetime import date

    scored_by_date = {
        date(2024, 1, 1): [(3.0, 0.03), (2.0, 0.02), (1.0, 0.01)],
        date(2024, 1, 2): [(3.0, 0.06), (2.0, 0.04), (1.0, 0.02)],
    }

    metrics = build_rank_signal_metrics(scored_by_date)

    # 分数与超额收益完全同序：IC 和 RankIC 应为满分正相关。
    assert metrics["ic_date_count"] == 2
    assert metrics["ic_mean"] == pytest.approx(1.0)
    assert metrics["rank_ic_mean"] == pytest.approx(1.0)
    assert metrics["rank_ic_positive_rate"] == pytest.approx(1.0)
    # 高分组超额减低分组超额，逐日 0.02 与 0.04 取均值。
    assert metrics["long_short_spread"] == pytest.approx(0.03)


def test_rank_signal_metrics_penalize_inverse_ordering() -> None:
    from datetime import date

    scored_by_date = {date(2024, 1, 1): [(3.0, 0.01), (2.0, 0.02), (1.0, 0.03)]}

    metrics = build_rank_signal_metrics(scored_by_date)

    assert metrics["ic_mean"] == pytest.approx(-1.0)
    assert metrics["rank_ic_mean"] == pytest.approx(-1.0)
    assert metrics["rank_ic_positive_rate"] == pytest.approx(0.0)
    assert metrics["long_short_spread"] == pytest.approx(-0.02)


def test_rank_signal_metrics_skip_uncorrelatable_dates() -> None:
    from datetime import date

    # 单标的日期无法算截面相关，零方差分数也不产生 IC。
    scored_by_date = {
        date(2024, 1, 1): [(1.0, 0.5)],
        date(2024, 1, 2): [(2.0, 0.01), (2.0, 0.02), (2.0, 0.03)],
    }

    metrics = build_rank_signal_metrics(scored_by_date)

    assert metrics["ic_date_count"] == 0
    assert metrics["ic_mean"] is None
    assert metrics["ic_ir"] is None
    assert metrics["rank_ic_positive_rate"] is None


def test_walk_forward_folds_roll_without_overlap() -> None:
    from datetime import date

    dates = [date(2024, 1, day) for day in range(1, 13)]
    folds = build_walk_forward_folds(dates, label_gap_days=5, min_train_dates=3, test_size=1)

    # 12 个日期，训练至少 3 天、gap 5 天后开始测试：首个测试日为索引 8。
    assert len(folds) == 4
    assert folds[0]["test_dates"] == [date(2024, 1, 9)]
    assert folds[-1]["test_dates"] == [date(2024, 1, 12)]
    # 扩张窗口：训练结束日随折递增，测试日不重叠。
    assert folds[0]["train_end"] == date(2024, 1, 3)
    assert folds[1]["train_end"] == date(2024, 1, 4)
    all_test = [day for fold in folds for day in fold["test_dates"]]
    assert len(all_test) == len(set(all_test))


def test_walk_forward_folds_skip_when_history_too_short() -> None:
    from datetime import date

    dates = [date(2024, 1, day) for day in range(1, 8)]
    assert build_walk_forward_folds(dates, label_gap_days=5, min_train_dates=3) == []


def test_walk_forward_metrics_cover_rolling_out_of_sample() -> None:
    bars = generate_sample_bars(days=40)
    features = compute_features(bars)
    labels = compute_labels(bars)

    metrics = build_walk_forward_metrics(features, labels)

    assert metrics["walk_forward_status"] == "ready"
    assert metrics["walk_forward_fold_count"] > 0
    # 滚动样本外应覆盖比单一测试窗更长的时间线。
    assert metrics["walk_forward_test_date_count"] >= 1
    assert metrics["walk_forward_ic_mean"] is not None
    assert metrics["walk_forward_rank_ic_mean"] is not None


def test_walk_forward_metrics_report_skip_without_history() -> None:
    bars = generate_sample_bars(days=8)
    metrics = build_walk_forward_metrics(compute_features(bars), compute_labels(bars))

    assert metrics["walk_forward_status"] == "skipped_insufficient_history"
    assert metrics["walk_forward_fold_count"] == 0


def test_baseline_metadata_reports_signal_metrics() -> None:
    bars = generate_sample_bars(days=40)
    metadata = train_baseline_model(compute_features(bars), compute_labels(bars))

    assert metadata.metrics is not None
    if metadata.evaluation_status == "ready":
        assert "ic_mean" in metadata.metrics
        assert "rank_ic_mean" in metadata.metrics
        assert "long_short_spread" in metadata.metrics


def test_feature_csv_read_round_trip(tmp_path: Path) -> None:
    rows = compute_features(generate_sample_bars(days=6))
    path = write_features_csv(tmp_path / "features.csv", rows)

    loaded = read_features_csv(path)

    assert len(loaded) == len(rows)
    assert loaded[1].symbol == rows[1].symbol
    assert loaded[1].trade_date == rows[1].trade_date
    assert loaded[1].return_1d == pytest.approx(rows[1].return_1d)
    assert loaded[-1].momentum_5d == pytest.approx(rows[-1].momentum_5d)
    assert loaded[-1].volatility_5d == pytest.approx(rows[-1].volatility_5d, abs=1e-8)
    assert loaded[-1].rsi_6 == pytest.approx(rows[-1].rsi_6, abs=1e-8)
    assert loaded[-1].macd_hist == pytest.approx(rows[-1].macd_hist, abs=1e-8)
