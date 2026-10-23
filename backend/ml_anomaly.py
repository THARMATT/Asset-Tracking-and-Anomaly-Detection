#!/usr/bin/env python3
"""
=============================================================================
IoT-Based Smart Asset Tracking — Experimental ML Anomaly Detection Layer
=============================================================================
This script implements an OPTIONAL second detection layer using Isolation
Forest to identify unusual movement patterns in event history.

IMPORTANT NOTICES:
- This script is EXPERIMENTAL and NOT authoritative for authorization decisions.
- Rule-based classification (anomaly_engine.py) remains the ground truth.
- This model uses SYNTHETIC training data because real operational data is
  insufficient (< 30 events). Synthetic-data performance does NOT establish
  real-world accuracy.
- Retrain only when substantial real event history is available (recommend
  ≥ 500 events spanning multiple weeks with diverse patterns).
- The system works fully WITHOUT this script and WITHOUT saved model files.

Usage:
  python ml_anomaly.py --mode train       # Train on synthetic+real data
  python ml_anomaly.py --mode evaluate    # Evaluate against labeled dataset
  python ml_anomaly.py --mode predict --asset_id A001  # Score one asset
  python ml_anomaly.py --mode demo        # Show how it works

Requirements:
  pip install scikit-learn pandas numpy joblib
=============================================================================
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

warnings.filterwarnings("ignore", category=FutureWarning)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ─── Optional dependencies ───────────────────────────────────────────────────
try:
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, confusion_matrix
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# ─── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "backend" / "asset_tracking.db"
MODEL_DIR = SCRIPT_DIR / "ml_artifacts"
MODEL_PATH = MODEL_DIR / "isolation_forest_v1.joblib"
SCALER_PATH = MODEL_DIR / "scaler_v1.joblib"
FEATURE_NAMES_PATH = MODEL_DIR / "feature_names_v1.json"
SYNTHETIC_SEED = 42

# Feature descriptions (for documentation and reproducibility)
FEATURE_DESCRIPTION = {
    "event_count_24h": "Number of scan events in last 24 hours for this asset",
    "gate_scans_24h": "Number of MAIN_GATE scans in last 24 hours",
    "distinct_zones_24h": "Number of distinct zones detected in last 24 hours",
    "avg_interval_minutes": "Average time between consecutive scans (minutes)",
    "min_interval_minutes": "Shortest interval between two consecutive scans (minutes)",
    "night_scan_ratio": "Fraction of scans occurring between 22:00 and 06:00 UTC",
    "zone_change_ratio": "Fraction of events that involve a zone change from previous scan",
    "is_authorized_exit": "Whether most recent gate scan was authorized (0/1)",
}


# ─── Data extraction from SQLite ──────────────────────────────────────────────

def load_events_from_db(db_path: Path = DB_PATH) -> Optional["pd.DataFrame"]:
    """Load event history from the live SQLite database."""
    if not ML_AVAILABLE:
        logger.error("scikit-learn/pandas not installed. Run: pip install scikit-learn pandas numpy joblib")
        return None
    if not db_path.exists():
        logger.error(f"Database not found at: {db_path}")
        return None

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        events = conn.execute("""
            SELECT event_id, asset_id, location, event_type, status,
                   timestamp, authorized, message_id
            FROM events
            ORDER BY timestamp ASC;
        """).fetchall()
        df = pd.DataFrame([dict(e) for e in events])
        logger.info(f"Loaded {len(df)} events from {db_path}")
        return df
    finally:
        conn.close()


def extract_features_per_asset(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Extract movement-pattern features per asset over the last 24h window.
    Returns a DataFrame with one row per asset, indexed by asset_id.

    Features are based on MOVEMENT PATTERNS, NOT on the status label
    (to avoid data leakage from rule-based labels into the ML model).
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    df24 = df[df["timestamp"] >= cutoff]

    records = []
    for asset_id, grp in df.groupby("asset_id"):
        grp24 = df24[df24["asset_id"] == asset_id].sort_values("timestamp")
        count_24h = len(grp24)
        gate_24h = int((grp24["location"] == "MAIN_GATE").sum())
        zones_24h = grp24["location"].nunique()

        intervals = []
        locs = grp24["location"].tolist()
        ts_list = grp24["timestamp"].tolist()
        if len(ts_list) > 1:
            for i in range(1, len(ts_list)):
                delta = (ts_list[i] - ts_list[i - 1]).total_seconds() / 60.0
                intervals.append(max(delta, 0.0))

        avg_interval = float(np.mean(intervals)) if intervals else 0.0
        min_interval = float(np.min(intervals)) if intervals else 0.0

        night_count = 0
        for ts in grp24["timestamp"]:
            if ts.hour < 6 or ts.hour >= 22:
                night_count += 1
        night_ratio = night_count / max(count_24h, 1)

        zone_changes = sum(1 for i in range(1, len(locs)) if locs[i] != locs[i - 1])
        zone_change_ratio = zone_changes / max(count_24h - 1, 1) if count_24h > 1 else 0.0

        # Whether most recent gate scan was authorized
        gate_events = grp24[grp24["location"] == "MAIN_GATE"].sort_values("timestamp")
        last_auth = int(gate_events["authorized"].iloc[-1]) if not gate_events.empty and gate_events["authorized"].iloc[-1] is not None else 0

        records.append({
            "asset_id": asset_id,
            "event_count_24h": count_24h,
            "gate_scans_24h": gate_24h,
            "distinct_zones_24h": zones_24h,
            "avg_interval_minutes": avg_interval,
            "min_interval_minutes": min_interval,
            "night_scan_ratio": night_ratio,
            "zone_change_ratio": zone_change_ratio,
            "is_authorized_exit": last_auth,
        })

    return pd.DataFrame(records)


# ─── Synthetic dataset generator ──────────────────────────────────────────────

def generate_synthetic_dataset(n_normal: int = 400, n_anomaly: int = 100, seed: int = SYNTHETIC_SEED) -> "pd.DataFrame":
    """
    Generate a clearly labelled synthetic dataset for training and evaluation.

    DISCLAIMER: This dataset is for demonstration and model structure validation
    only. It does NOT reflect observed behavior in this specific facility and
    cannot be used to claim validated anomaly detection accuracy.

    Normal patterns: 1-3 scans/day, 0-1 gate scans, 1-2 zones, intervals ≥ 30 min
    Anomaly patterns: high frequency, midnight scans, rapid zone changes, gate scans
    """
    rng = np.random.default_rng(seed)

    def make_normal(n):
        return pd.DataFrame({
            "event_count_24h": rng.integers(1, 4, n),
            "gate_scans_24h": rng.integers(0, 2, n),
            "distinct_zones_24h": rng.integers(1, 3, n),
            "avg_interval_minutes": rng.uniform(30, 480, n),
            "min_interval_minutes": rng.uniform(20, 120, n),
            "night_scan_ratio": rng.uniform(0.0, 0.1, n),
            "zone_change_ratio": rng.uniform(0.0, 0.3, n),
            "is_authorized_exit": rng.integers(0, 2, n),
            "label": 1,  # 1 = normal (sklearn Isolation Forest convention: 1=inlier)
        })

    def make_anomaly(n):
        return pd.DataFrame({
            "event_count_24h": rng.integers(8, 25, n),
            "gate_scans_24h": rng.integers(2, 8, n),
            "distinct_zones_24h": rng.integers(3, 5, n),
            "avg_interval_minutes": rng.uniform(1, 15, n),
            "min_interval_minutes": rng.uniform(0.1, 5, n),
            "night_scan_ratio": rng.uniform(0.4, 1.0, n),
            "zone_change_ratio": rng.uniform(0.6, 1.0, n),
            "is_authorized_exit": rng.integers(0, 2, n),
            "label": -1,  # -1 = anomaly (sklearn convention)
        })

    df = pd.concat([make_normal(n_normal), make_anomaly(n_anomaly)], ignore_index=True)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


# ─── Training ─────────────────────────────────────────────────────────────────

def train_model(db_path: Path = DB_PATH) -> None:
    """Train Isolation Forest on synthetic dataset, optionally enriched with real data."""
    if not ML_AVAILABLE:
        logger.error("ML dependencies not available. Run: pip install scikit-learn pandas numpy joblib")
        sys.exit(1)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Generating synthetic training dataset (seed=%d)...", SYNTHETIC_SEED)
    synth_df = generate_synthetic_dataset(n_normal=400, n_anomaly=100)
    feature_cols = [c for c in synth_df.columns if c != "label"]

    # Try to augment with real data (treated as normal if no label)
    real_df = load_events_from_db(db_path)
    if real_df is not None and not real_df.empty and len(real_df) >= 5:
        feat_df = extract_features_per_asset(real_df)
        if not feat_df.empty:
            logger.info(f"Augmenting with {len(feat_df)} real asset feature rows (treated as normal)")
            feat_df["label"] = 1
            feat_df = feat_df[feature_cols + ["label"]]
            synth_df = pd.concat([synth_df, feat_df], ignore_index=True)

    X = synth_df[feature_cols].values
    y = synth_df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=SYNTHETIC_SEED, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    contamination = round(100 / 500, 3)
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=SYNTHETIC_SEED,
        n_jobs=-1,
    )
    model.fit(X_train_scaled)

    y_pred = model.predict(X_test_scaled)

    logger.info("\n=== Isolation Forest Evaluation on Synthetic Test Set ===")
    logger.info("NOTE: These metrics reflect SYNTHETIC data only. Not valid for real-world claims.\n")
    print(classification_report(y_test, y_pred, target_names=["anomaly(-1)", "normal(+1)"], labels=[-1, 1]))
    print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred, labels=[-1, 1]))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    with open(FEATURE_NAMES_PATH, "w") as f:
        json.dump(feature_cols, f)

    logger.info(f"\nModel saved to: {MODEL_PATH}")
    logger.info(f"Scaler saved to: {SCALER_PATH}")
    logger.info("Training complete. REMINDER: Retrain with ≥500 real labeled events before citing accuracy.")


# ─── Prediction ───────────────────────────────────────────────────────────────

def predict_for_asset(asset_id: str, db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Score a single asset's recent movement pattern with the trained model."""
    if not ML_AVAILABLE:
        return {"error": "ML dependencies not available", "ml_available": False}

    if not MODEL_PATH.exists():
        return {"error": "Model not trained yet. Run: python ml_anomaly.py --mode train", "ml_available": True}

    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    with open(FEATURE_NAMES_PATH) as f:
        feature_cols = json.load(f)

    real_df = load_events_from_db(db_path)
    if real_df is None or real_df.empty:
        return {"error": "No event data available", "ml_available": True}

    asset_df = real_df[real_df["asset_id"] == asset_id]
    if asset_df.empty:
        return {"error": f"No events found for asset '{asset_id}'", "ml_available": True}

    feat_df = extract_features_per_asset(asset_df)
    if feat_df.empty:
        return {"error": "Could not extract features", "ml_available": True}

    X = feat_df[feature_cols].values
    X_scaled = scaler.transform(X)
    prediction = model.predict(X_scaled)[0]
    score = model.score_samples(X_scaled)[0]

    return {
        "asset_id": asset_id,
        "ml_prediction": "NORMAL" if prediction == 1 else "SUSPICIOUS_PATTERN",
        "anomaly_score": round(float(score), 4),
        "features": feat_df[feature_cols].iloc[0].to_dict(),
        "disclaimer": (
            "This is an EXPERIMENTAL ML signal only. "
            "It does NOT override the rule-based authorization decision. "
            "Trained on synthetic data — accuracy for real operations is unknown."
        ),
        "ml_available": True,
    }


# ─── Evaluation ───────────────────────────────────────────────────────────────

def evaluate_model() -> None:
    """Evaluate trained model on a fresh synthetic evaluation set."""
    if not ML_AVAILABLE:
        logger.error("ML dependencies not available.")
        return
    if not MODEL_PATH.exists():
        logger.error("No trained model found. Run --mode train first.")
        return

    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    with open(FEATURE_NAMES_PATH) as f:
        feature_cols = json.load(f)

    # Use a different seed for evaluation (no data leakage)
    eval_df = generate_synthetic_dataset(n_normal=100, n_anomaly=25, seed=SYNTHETIC_SEED + 1)
    X_eval = eval_df[feature_cols].values
    y_eval = eval_df["label"].values
    X_eval_scaled = scaler.transform(X_eval)
    y_pred = model.predict(X_eval_scaled)

    print("\n=== Model Evaluation on Fresh Synthetic Evaluation Set ===")
    print("DISCLAIMER: Performance on synthetic data does not predict real-world accuracy.\n")
    print(classification_report(y_eval, y_pred, target_names=["anomaly(-1)", "normal(+1)"], labels=[-1, 1]))
    print("Confusion Matrix:\n", confusion_matrix(y_eval, y_pred, labels=[-1, 1]))


# ─── Demo ─────────────────────────────────────────────────────────────────────

def demo_mode() -> None:
    """Display feature descriptions and explain the ML layer design."""
    print("\n" + "=" * 70)
    print("IoT Asset Tracking — ML Anomaly Detection Layer (EXPERIMENTAL)")
    print("=" * 70)
    print("\nThis layer adds OPTIONAL movement-pattern scoring to the system.")
    print("It does NOT replace or override rule-based anomaly detection.\n")
    print("Layer 1 (Authoritative): Rule-based anomaly_engine.py")
    print("  - NORMAL, MISPLACED, AUTHORIZED_EXIT, UNAUTHORIZED_EXIT, etc.")
    print("\nLayer 2 (Experimental): Isolation Forest (this script)")
    print("  - Looks for unusual movement PATTERNS, not individual events")
    print("  - Trained on synthetic data; field accuracy is unverified\n")
    print("Features extracted per asset over a rolling 24-hour window:")
    for feat, desc in FEATURE_DESCRIPTION.items():
        print(f"  {feat:30s}: {desc}")
    print(f"\nML available: {ML_AVAILABLE}")
    print(f"Model file:   {MODEL_PATH} (exists: {MODEL_PATH.exists()})")
    print("=" * 70)


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Optional ML anomaly detection layer for IoT Asset Tracking"
    )
    parser.add_argument("--mode", choices=["train", "evaluate", "predict", "demo"], default="demo")
    parser.add_argument("--asset_id", help="Asset ID for --mode predict")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to SQLite database")
    args = parser.parse_args()

    db = Path(args.db)

    if args.mode == "demo":
        demo_mode()
    elif args.mode == "train":
        train_model(db)
    elif args.mode == "evaluate":
        evaluate_model()
    elif args.mode == "predict":
        if not args.asset_id:
            logger.error("--asset_id is required for --mode predict")
            sys.exit(1)
        result = predict_for_asset(args.asset_id, db)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
