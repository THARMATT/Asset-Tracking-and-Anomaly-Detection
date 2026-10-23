# Advanced Anomaly Detection Evaluation & Movement Pattern Analysis
## Layer 2: Experimental Movement Pattern Analysis (Isolation Forest)

**Project:** IoT-Based Smart Asset Tracking and Anomaly Detection System  
**Document Version:** 1.0.0  
**Date:** 2026-10-23  

---

## 1. Executive Summary & Defensibility Assessment

In accordance with academic rigor and the project specification:

> [!IMPORTANT]
> **Data Sufficiency Assessment:**  
> The current SQLite database contains only **15 historical scan events** across 5 registered assets (ranging from 1 to 5 scans per asset). Training an unsupervised machine learning model (such as an Isolation Forest) on 15 records is **statistically invalid** and would lead to severe overfitting and arbitrary decision boundaries.
> 
> Therefore, **Machine Learning is strictly treated as an OPTIONAL, EXPERIMENTAL Layer 2 pattern scoring capability**, completely decoupled from the primary, authoritative, deterministic Layer 1 anomaly detection engine.

---

## 2. Detection Architecture: Dual-Layer Defense

```
[ Incoming Telemetry Event (MQTT / REST) ]
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│  LAYER 1: Authoritative Deterministic Rules Engine     │
│  (backend/anomaly_engine.py)                           │
├────────────────────────────────────────────────────────┤
│  • NORMAL                   (Expected storage zone)    │
│  • MISPLACED                (Unexpected internal shelf)│
│  • AUTHORIZED_EXIT          (MAIN_GATE + valid permit) │
│  • UNAUTHORIZED_EXIT        (MAIN_GATE + denied/expired)
│  • UNKNOWN_ASSET            (Uncataloged RFID tag)     │
│  • MISSING_INVESTIGATION    (Inventory audit omission) │
└──────────────────────────┬─────────────────────────────┘
                           │ Authoritative Result Saved to SQLite
                           ▼
┌────────────────────────────────────────────────────────┐
│  LAYER 2: Experimental Movement Pattern Analysis       │
│  (backend/ml_anomaly.py) - OPTIONAL                   │
├────────────────────────────────────────────────────────┤
│  • Evaluates multi-scan aggregate features over a 24h  │
│    sliding window per asset (not single scans)         │
│  • Generates: "NORMAL" vs "SUSPICIOUS_PATTERN" score   │
│  • DOES NOT override Layer 1 authorization decisions   │
│  • System functions 100% cleanly without ML dependencies│
└────────────────────────────────────────────────────────┘
```

---

## 3. Layer 2 Feature Engineering

To prevent data leakage and avoid trivially encoding the rule-based target labels, **features are computed from physical movement dynamics across a 24-hour window**, rather than individual scan status:

| Feature Name | Type | Description | Rationale |
|:---|:---:|:---|:---|
| `event_count_24h` | Integer | Total scans for the asset in last 24h | Identifies unusually high physical handling or scanning loops |
| `gate_scans_24h` | Integer | Scans at `MAIN_GATE` in last 24h | Unusually frequent perimeter scans may indicate reconnaissance |
| `distinct_zones_24h`| Integer | Count of unique zones visited in 24h | High zone hopping indicates erratic relocation |
| `avg_interval_minutes`| Float | Mean time elapsed between consecutive scans | Identifies rapid sequential transfers |
| `min_interval_minutes`| Float | Minimum interval between consecutive scans | Distinguishes human handling from telemetry bursts |
| `night_scan_ratio` | Float | Ratio of scans occurring between 22:00-06:00 UTC | Flags off-hours activity |
| `zone_change_ratio` | Float | Fraction of transitions between different zones | Distinguishes stationary items from roaming assets |
| `is_authorized_exit` | Binary (0/1)| Most recent gate authorization status | Contextual authorization feature |

> **Anti-Leakage Safeguard:** The model does NOT use `asset_id` as a numerical measurement, nor does it consume the Layer 1 `status` field as an input feature.

---

## 4. Synthetic Evaluation Protocol

Because real event data is currently insufficient for training, `backend/ml_anomaly.py` provides a reproducible synthetic dataset generator (`generate_synthetic_dataset`) with a fixed seed (`seed=42`):
- **Normal Distribution ($N=400$):** 1–3 scans/day, 0–1 gate scans, 1–2 zones, scan intervals between 30 and 480 minutes, negligible night activity (< 10%).
- **Anomalous Distribution ($N=100$):** 8–25 scans/day, 2–8 gate scans, 3–5 zones, rapid scan intervals (< 15 min), heavy off-hours activity (> 40%).

### Synthetic Validation Results (Seed = 42, 80/20 Stratified Split)

```text
               precision    recall  f1-score   support

  anomaly(-1)       0.95      0.90      0.92        20
   normal(+1)       0.98      0.99      0.98        80

     accuracy                           0.97       100
    macro avg       0.96      0.94      0.95       100
 weighted avg       0.97      0.97      0.97       100
```

> [!WARNING]
> **Academic Integrity Notice:**  
> These metrics reflect performance on **mathematically synthesized data**. They demonstrate that the feature extraction pipeline and Isolation Forest hyperparameters are mathematically functional, but **they do not establish real-world detection accuracy**. Field validation requires gathering at least 500 real operational events across several weeks of facility operations.

---

## 5. Software Safeguards & Modularity

1. **Clean Fallback:** `ml_anomaly.py` uses defensive try-except import blocks. If `scikit-learn` or `pandas` are not installed in the deployment environment:
   - All unit tests in `test_ml_anomaly.py` cleanly skip or pass without errors.
   - The Flask backend REST API, SQLite database, MQTT subscriber, and React dashboard operate with 100% full functionality.
2. **Artifact Versioning:** Model and scaler weights are saved under `backend/ml_artifacts/` with explicit version suffixes (`isolation_forest_v1.joblib`, `scaler_v1.joblib`, `feature_names_v1.json`).
3. **No Retraining on Telemetry Ingestion:** The subscriber never triggers model retraining during runtime message handling, ensuring sub-millisecond event ingestion latency.
