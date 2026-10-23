"""
Tests for Stage 08: ML Anomaly Detection Layer (ml_anomaly.py).
Tests missing features, invalid data, and unavailable model scenarios.
"""
import json
import pytest
import sys
import os
from pathlib import Path

# Ensure backend module resolution
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Check ML availability without importing broken ─────────────────────────
def test_ml_module_imports_cleanly():
    """ml_anomaly.py must import without raising even if sklearn is missing."""
    import importlib
    spec = importlib.util.find_spec("backend.ml_anomaly")
    # Just importing should not raise
    try:
        from backend import ml_anomaly  # noqa: F401
    except ImportError:
        # If ml_anomaly can't import due to path issues, import directly
        import ml_anomaly  # noqa: F401


def test_predict_no_model_returns_error(tmp_path):
    """predict_for_asset must return error dict when model file does not exist."""
    try:
        import ml_anomaly
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ml_anomaly",
            Path(__file__).parent.parent / "ml_anomaly.py"
        )
        ml_anomaly = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ml_anomaly)

    # Point to a temp DB with no model
    result = ml_anomaly.predict_for_asset("A001", db_path=tmp_path / "nonexistent.db")
    assert "error" in result


def test_feature_extraction_empty_df():
    """extract_features_per_asset must return empty DataFrame for empty input."""
    try:
        import pandas as pd
        import ml_anomaly
    except ImportError:
        pytest.skip("pandas or ml_anomaly not available")

    result = ml_anomaly.extract_features_per_asset(pd.DataFrame())
    assert result.empty


def test_synthetic_dataset_shape_and_labels():
    """Synthetic dataset must have correct shape and only labels -1 and 1."""
    try:
        import ml_anomaly
    except ImportError:
        pytest.skip("ml_anomaly not available")

    if not getattr(ml_anomaly, "ML_AVAILABLE", False):
        pytest.skip("numpy/pandas/scikit-learn not installed in test environment")

    df = ml_anomaly.generate_synthetic_dataset(n_normal=50, n_anomaly=10)
    assert len(df) == 60
    assert set(df["label"].unique()).issubset({-1, 1})
    assert "event_count_24h" in df.columns
    assert "gate_scans_24h" in df.columns


def test_ml_optional_system_still_functions(temp_db):
    """Backend event processing must work without any ML dependencies or model."""
    from anomaly_engine import process_and_save_scan_event

    result = process_and_save_scan_event(
        {"asset_id": "A001", "location": "SHELF_01", "message_id": "ml-test-001"},
        db_path=temp_db
    )
    assert result["status"] == "NORMAL"
    assert result["persistence"]["event_id"] is not None


def test_feature_names_documented():
    """Feature descriptions dict must exist and cover all numeric features."""
    try:
        import ml_anomaly
    except ImportError:
        pytest.skip("ml_anomaly not available")

    assert isinstance(ml_anomaly.FEATURE_DESCRIPTION, dict)
    assert len(ml_anomaly.FEATURE_DESCRIPTION) >= 7
    assert "gate_scans_24h" in ml_anomaly.FEATURE_DESCRIPTION
    assert "night_scan_ratio" in ml_anomaly.FEATURE_DESCRIPTION
