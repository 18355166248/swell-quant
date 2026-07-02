from pathlib import Path

import duckdb

from swell_quant.data.sample_data import generate_sample_bars, write_price_bars_csv
from swell_quant.research.features import compute_features, write_features_csv
from swell_quant.research.labels import compute_labels, write_labels_csv
from swell_quant.research.modeling import (
    generate_historical_predictions,
    generate_predictions,
    write_predictions_csv,
)
from swell_quant.storage.duckdb_mirror import mirror_pipeline_csvs_to_duckdb


def test_mirror_pipeline_csvs_to_duckdb_replaces_tables(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    bars = generate_sample_bars(days=8)
    features = compute_features(bars)
    labels = compute_labels(bars)
    predictions = generate_predictions(features)
    historical_predictions = generate_historical_predictions(features)

    write_price_bars_csv(data_dir / "raw" / "sample_prices.csv", bars)
    write_features_csv(data_dir / "processed" / "sample_features.csv", features)
    write_labels_csv(data_dir / "processed" / "sample_labels.csv", labels)
    write_predictions_csv(data_dir / "processed" / "latest_predictions.csv", predictions)
    write_predictions_csv(data_dir / "processed" / "historical_predictions.csv", historical_predictions)

    result = mirror_pipeline_csvs_to_duckdb(data_dir, data_dir / "duckdb" / "swell_quant.duckdb")

    assert result.total_rows == len(bars) + len(features) + len(labels) + len(predictions) + len(
        historical_predictions
    )
    assert {table.table_name for table in result.tables} == {
        "raw_prices",
        "feature_rows",
        "label_rows",
        "latest_predictions",
        "historical_predictions",
    }
    with duckdb.connect(str(result.duckdb_path), read_only=True) as connection:
        raw_count = connection.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]
        feature_count = connection.execute("SELECT COUNT(*) FROM feature_rows").fetchone()[0]
        prediction_count = connection.execute("SELECT COUNT(*) FROM latest_predictions").fetchone()[0]

    assert raw_count == len(bars)
    assert feature_count == len(features)
    assert prediction_count == len(predictions)
