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
    build_training_samples,
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
