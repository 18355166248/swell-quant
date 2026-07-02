from pathlib import Path

import pytest

from swell_quant.data.sample_data import generate_sample_bars
from swell_quant.research.features import compute_features, read_features_csv, write_features_csv
from swell_quant.research.labels import compute_labels
from swell_quant.research.modeling import (
    BASELINE_MODEL_VERSION,
    generate_historical_predictions,
    generate_predictions,
    train_baseline_model,
)


def test_baseline_model_metadata_uses_labeled_rows() -> None:
    bars = generate_sample_bars(days=20)
    features = compute_features(bars)
    labels = compute_labels(bars)

    metadata = train_baseline_model(features, labels)

    assert metadata.model_version == BASELINE_MODEL_VERSION
    assert metadata.model_type == "rule_baseline"
    assert metadata.train_start == "2024-01-02"
    assert metadata.train_end == "2024-01-16"
    assert metadata.prediction_date == "2024-01-21"
    assert metadata.disclaimer == "仅用于研究，不构成投资建议"


def test_generate_predictions_ranks_latest_date_only() -> None:
    features = compute_features(generate_sample_bars(days=20))
    predictions = generate_predictions(features)

    assert len(predictions) == 3
    assert {row.trade_date.isoformat() for row in predictions} == {"2024-01-21"}
    assert [row.rank for row in predictions] == [1, 2, 3]
    assert predictions[0].score >= predictions[1].score >= predictions[2].score


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
