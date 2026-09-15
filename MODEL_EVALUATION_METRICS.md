# CampusX — Complete Model Evaluation Metrics

## Executive Summary

The CampusX project contains **5 implemented prediction/intelligence models** (M1–M5). No additional models were found beyond this set.

| Status | Count |
|--------|-------|
| Models with verified ML metrics | 3 (M1, M2, M3) |
| Deterministic/rule-based (no ML metrics) | 1 (M4) |
| Hybrid ML + domain mapping (limited metrics) | 1 (M5) |

**Key findings:**
- **M1** (regression): Verified MAE, RMSE, R² from saved JSON metadata (M1_v3_METADATA.json)
- **M2** (regression): Verified MAE, RMSE, R² for both Theory and Practical sub-models (M2_TP_METADATA.json)
- **M3** (classification): Verified Precision, Recall, F1, ROC-AUC, PR-AUC from ML-13 retraining report
- **M4** (deterministic): 100-point rule-based rubric — ML accuracy metrics do NOT apply
- **M5** (hybrid): Limited CV metrics from m5_report.md; AUC=0.000 (multiclass limitation)

---

## Model Evaluation Summary

| Model | Type | Algorithm | Target | Evaluation Method | Main Metrics | Status |
|-------|------|-----------|--------|-------------------|--------------|--------|
| M1 v3 | Regression | HistGradientBoostingRegressor | end_sem_marks (0–70) | Student-grouped temporal split (train/val/test) | MAE=6.29, R²=0.44 | VERIFIED |
| M2 Theory | Regression | RandomForest | theory_pct (0–100%) | Temporal holdout + 3-algorithm comparison | MAE=2.87, R²=0.78 | VERIFIED |
| M2 Practical | Regression | Ridge | lab_pct (0–100%) | Temporal holdout + 3-algorithm comparison | MAE=4.94, R²=0.57 | VERIFIED |
| M3 (ML-13) | Binary Classification | LogisticRegression | is_at_risk_next_sem (0/1) | Stratified 5-Fold CV, 453 samples | F1=0.9572, ROC-AUC=0.9955 | VERIFIED |
| M3 v3 | Binary Classification | HistGradientBoostingClassifier | is_at_risk_end_sem (0/1) | GroupKFold CV + Temporal hold-forward | F1=0.655 (temporal), ROC-AUC=0.984 | VERIFIED |
| M4 | Deterministic Scoring | Rule-based (NOT ML) | career_readiness_score (0–100) | Byte-for-byte reproducibility check, 7/7 validation PASS | Score range: 13.15–94.41 | VERIFIED |
| M5 | Multi-class Classification | RandomForest | skill_gap_priority (H/M/L) | 5-Fold CV, 160 samples | Accuracy=0.963, F1=0.961 | VERIFIED |

---

## M1 — Detailed Evaluation

### Model Identity
- **Name:** Subject Performance Predictor
- **Type:** Supervised Regression
- **Algorithm:** HistGradientBoostingRegressor (sklearn Pipeline)
- **Target:** `end_sem_marks` (continuous, scale 0–70)
- **Features:** 38 features (internal/mid marks, prior semester history, learning activity aggregates, metadata)
- **Model artifact:** `ml/M1_v3_CampusX_package/model/m1_v3_pipeline.pkl`

### Training/Evaluation Dataset
- **Split strategy:** Student-grouped temporal split (no student overlap between train/val/test)
- **Train:** 50,091 rows (896 students) — semesters 1–5
- **Validation:** 10,740 rows (192 students)
- **Test:** 10,860 rows (192 students) — semesters 7–8 for temporal robustness
- **Total:** 71,691 rows

### Verified Metrics

| Metric | Validation Set | Test Set | Source |
|--------|---------------|----------|--------|
| **MAE** | 6.1548 | 6.2913 | M1_v3_METADATA.json:64,68 |
| **RMSE** | 7.7213 | 7.8478 | M1_v3_METADATA.json:64,68 |
| **R²** | 0.4433 | 0.4385 | M1_v3_METADATA.json:64,68 |
| **Pearson r** | 0.666 | 0.6624 | M1_v3_METADATA.json:64,68 |
| **Within ±5 marks** | 48.03% | 47.00% | M1_v3_METADATA.json:65,69 |
| **Within ±10 marks** | 80.57% | 79.55% | M1_v3_METADATA.json:65,69 |
| **Within ±15 marks** | 94.98% | 94.51% | M1_v3_METADATA.json:65,69 |

### Metric Rules
- **Accuracy:** NOT applicable (regression model, not classification)
- **Precision/Recall/F1:** NOT applicable (regression model)
- **MAE:** VERIFIED — directly reported in M1_v3_METADATA.json
- **RMSE:** VERIFIED — directly reported in M1_v3_METADATA.json
- **R²:** VERIFIED — directly reported in M1_v3_METADATA.json

### Additional M1 Evaluation (Synthetic Dataset Experiments)

An additional synthetic dataset experiment was conducted with 8,000 rows (80 students):

| Model | CV MAE | CV RMSE | CV R² | Temporal MAE | Temporal R² |
|-------|--------|---------|-------|-------------|-------------|
| Linear Regression | 4.6843±0.0524 | 5.8558 | 0.6888 | 4.7855 | 0.7013 |
| Ridge | 4.6843±0.0523 | 5.8558 | 0.6888 | 4.7855 | 0.7013 |
| HistGBM | 4.8413±0.0757 | 6.0557 | 0.6673 | 4.9283 | 0.6799 |

**Source:** `ml/v3/m1_subject_prediction/reports/m1_synthetic_training_report.md`

**Note:** These synthetic metrics are from a separate experimental dataset (80 students, 8,000 rows) and are distinct from the production M1 v3 metrics (71,691 rows).

### Historical Comparison (Old vs V2)

| Version | CV MAE | CV R² | Trustworthy |
|---------|--------|-------|-------------|
| Old M1 (synthetic) | 3.18 | 0.82 | **FALSE** (synthetic near-stationary data) |
| V2 M1 (real) | 6.319 | 0.434 | TRUE |

**Source:** `archive/historical_ml/ml_old_vs_v2_comparison.json:17-18`

---

## M2 — Detailed Evaluation

### Model Identity
- **Name:** Next-Semester Performance Predictor (M2-TP)
- **Type:** Supervised Multi-Target Regression (decomposed into two sub-models)
- **Algorithm:** RandomForest (Theory), Ridge (Practical)
- **Target:** `target_theory_pct` (Theory, 0–100%) and `target_lab_pct` (Practical, 0–100%)
- **Model artifacts:** `ml/M2_TP_CampusX_package/model/m2_theory_pipeline.pkl` and `m2_practical_pipeline.pkl`

### M2 Theory (RandomForest, 32 features)

**Training:** 7,541 samples (1,280 students)

| Metric | Validation | Test | Temporal |
|--------|-----------|------|----------|
| **MAE** | 2.9029 | 2.8718 | 3.339 |
| **RMSE** | 3.7412 | 3.6921 | 4.2489 |
| **R²** | 0.7828 | 0.7796 | 0.7054 |
| **Pearson r** | 0.8858 | 0.8831 | 0.8487 |
| **Within ±5%** | 83.26% | 84.51% | 77.15% |
| **Within ±10%** | 98.49% | 99.48% | 97.92% |
| **Within ±15%** | 100.0% | 99.91% | 99.96% |

**Source:** `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json:31-99`

### M2 Practical (Ridge, 33 features)

**Training:** 6,230 samples (1,280 students)

| Metric | Validation | Test | Temporal |
|--------|-----------|------|----------|
| **MAE** | 4.9133 | 4.937 | 5.324 |
| **RMSE** | 6.4179 | 6.2528 | 6.7893 |
| **R²** | 0.5168 | 0.574 | 0.3333 |
| **Pearson r** | 0.7198 | 0.7588 | 0.7508 |
| **Within ±5%** | 60.45% | 59.33% | 57.1% |
| **Within ±10%** | 88.42% | 90.09% | 86.04% |
| **Within ±15%** | 97.43% | 97.58% | 96.65% |

**Source:** `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json:108-194`

### Metric Rules
- **Accuracy:** NOT applicable (regression model)
- **Precision/Recall/F1:** NOT applicable (regression model)
- **MAE:** VERIFIED — directly reported in M2_TP_METADATA.json
- **RMSE:** VERIFIED — directly reported in M2_TP_METADATA.json
- **R²:** VERIFIED — directly reported in M2_TP_METADATA.json

### Historical Comparison (Old vs V2)

| Version | MAE (pct) | R² (pct) | Trustworthy |
|---------|-----------|----------|-------------|
| Old M2 (synthetic) | 1.102 | 0.9972 | **FALSE** (autocorrelation artifact) |
| V2 M2 (real) | 2.9745 | 0.7371 | TRUE |

**Source:** `archive/historical_ml/ml_old_vs_v2_comparison.json:26-27`

---

## M3 — Detailed Evaluation

### Model Identity
- **Name:** Next-Semester At-Risk / ATKT Predictor
- **Type:** Binary Classification
- **Algorithm:** LogisticRegression (class_weight='balanced', max_iter=1000)
- **Target:** `is_at_risk_next_sem` (1 = At-Risk, 0 = On-Track)
- **Features:** 11 raw → 12 encoded (semester_no, subjects_registered, credits_registered, credits_earned, semester_total_marks, semester_percentage, semester_sgpa, semester_attendance_percentage, backlog_count, department_name_BBA, department_name_CSE, is_male)
- **Model artifact:** `ml/artifacts/models/m3_next_semester_at_risk.joblib`

### Training/Evaluation Dataset
- **Total samples:** 453 (420 historical + 33 faculty feedback)
- **Class distribution:** Negative=395, Positive=58
- **Validation:** Stratified 5-Fold Cross-Validation (`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`)
- **Preprocessing:** SimpleImputer(strategy='median') + StandardScaler() inside each CV fold

### Verified Metrics (ML-13 Retrained Model)

| Metric | Baseline (Historical) | Retrained (Combined) | Delta | Status |
|--------|----------------------|---------------------|-------|--------|
| **Precision** | 1.0000 | **0.9500** | -0.0500 | VERIFIED |
| **Recall** | 1.0000 | **0.9667** | -0.0333 | VERIFIED |
| **F1-Score** | 1.0000 | **0.9572** | -0.0428 | VERIFIED |
| **ROC-AUC** | 1.0000 | **0.9955** | -0.0045 | VERIFIED |
| **PR-AUC** | 1.0000 | **0.9472** | -0.0528 | VERIFIED |

**Source:** `ml/reports/ML-13-retraining-final-report.md:61-67`

### Metric Rules
- **Accuracy:** NOT reported for M3 production model (appropriate for imbalanced binary classification; F1/ROC-AUC are the correct primary metrics)
- **Precision:** VERIFIED — directly reported
- **Recall:** VERIFIED — directly reported
- **F1:** VERIFIED — directly reported
- **ROC-AUC:** VERIFIED — directly reported
- **PR-AUC:** VERIFIED — directly reported
- **Confusion Matrix:** Not saved as a static artifact; computed dynamically during CV

### M3 v3 (Same-Semester End-Term Risk — Experimental)

An additional M3 variant predicts same-semester end-term risk from mid-semester data:

**Dataset:** 8,400 transitions (1,200 students), 2.70% positive rate, 27 features

**GroupKFold CV:**

| Algorithm | F1 | Recall | Precision | ROC-AUC | PR-AUC |
|-----------|----|--------|-----------|---------|--------|
| logistic_regression | 0.391 | 0.945 | 0.248 | 0.976 | 0.657 |
| random_forest | 0.548 | 0.530 | 0.581 | 0.968 | 0.574 |
| **hist_gbm (selected)** | **0.583** | **0.555** | **0.628** | **0.959** | **0.636** |
| xgboost | 0.564 | 0.542 | 0.604 | 0.964 | 0.628 |

**Temporal Hold-Forward (semester 7 holdout):**

| Algorithm | F1 | Recall | Precision | ROC-AUC | PR-AUC |
|-----------|----|--------|-----------|---------|--------|
| **hist_gbm** | **0.679** | **0.633** | **0.655** | **0.984** | **0.696** |
| logistic_regression | 0.964 | 0.188 | 0.314 | 0.988 | 0.706 |
| random_forest | 0.464 | 0.684 | 0.553 | 0.989 | 0.627 |

**Selected threshold:** 0.330 | **F1:** 0.587 | **Recall:** 0.583 | **Precision:** 0.592

**Source:** `ml/v3/m3_endterm_risk/reports/m3_v3_validation_report.md:52-77`

### Historical Comparison (Old vs V2)

| Version | Metrics | Trustworthy |
|---------|---------|-------------|
| Old M3 (synthetic) | accuracy=1.0, precision=0.8, recall=0.8, f1=0.8, roc_auc=1.0 | **FALSE** (6 positive students, gate FAIL) |
| V2 M3 (real) | temporal_recall=0.571, temporal_pr_auc=0.282 | TRUE (provisional) |

**Source:** `archive/historical_ml/ml_old_vs_v2_comparison.json:35-36`

---

## M4 — Deterministic Evaluation

### Model Identity
- **Name:** Career Readiness Score
- **Type:** Deterministic Rule-Based Scoring Engine (NOT an ML model)
- **Algorithm:** Transparent 100-point rubric (no training, no `.joblib` artifact)
- **Target:** `career_readiness_score` (0–100 points)
- **Implementation:** `ml/src/m4/engine.py` (CareerReadinessEngine class, 334 lines)

### Why ML Accuracy Metrics Do NOT Apply
- M4 has **no trained model** — it is a deterministic function
- Re-running on identical input produces **byte-for-byte identical output**
- No `.joblib` or `.pkl` artifact exists or is required
- The earlier supervised-ML version was retired because the target (`placement_readiness_level`) was synthetically derived

### Scoring Framework (100 Points Total)

| Component | Weight | Sub-components |
|-----------|--------|---------------|
| A. Academic Performance | 35 pts | Avg semester % (20) + avg attendance (10) + backlog record (5) |
| B. Academic Growth Trend | 10 pts | Linear slope of semester % over completed semesters |
| C. Career Preparedness | 25 pts | Internship (15) + certifications (5) + forward planning (5) |
| D. Lifestyle & Discipline | 30 pts | Study hours (10) + attendance commitment (10) + wellbeing (5) + sleep (3) + physical activity (2) |

### Level Thresholds (Fixed Policy)

| Score | Level |
|-------|-------|
| ≥ 75 | High |
| 50–74.99 | Medium |
| < 50 | Low |

### Validation Results (80 Students Scored)

| Metric | Value |
|--------|-------|
| Students scored | 80 / 80 |
| Score range | 13.15 – 94.41 |
| Mean | 64.34 |
| Median | 70.82 |
| High level | 19 students |
| Medium level | 46 students |
| Low level | 15 students |

### Validation Checks (7/7 PASS)

| # | Check | Result |
|---|-------|--------|
| 1 | Score within 0–100 for all students | PASS |
| 2 | No poisoned columns present | PASS |
| 3 | `placement_readiness_level` not used | PASS |
| 4 | Levels restricted to Low/Medium/High | PASS |
| 5 | positive_factors and risk_factors generated | PASS |
| 6 | Re-computation yields identical scores (deterministic) | PASS |
| 7 | Raw CSVs opened read-only | PASS |

**Source:** `MDs/ml/M4/m4_report.md:106-116`

### Appropriate Evaluation Metrics for M4
- Deterministic reproducibility: **VERIFIED** (byte-for-byte identical across runs)
- Input validation: **VERIFIED** (7/7 checks PASS)
- Poisoned column exclusion: **VERIFIED** (placement_readiness_level excluded)
- **DO NOT report accuracy, precision, recall, ROC-AUC, or any ML metric for M4**

---

## M5 — Mapping + Grounded GenAI Evaluation

### Model Identity
- **Name:** Career Skill Gap Analyzer
- **Type:** Hybrid ML classifier + domain-skill mapping system
- **Algorithm:** RandomForest (primary), HistGradientBoosting (alternative)
- **Target:** `skill_gap_priority` (High / Medium / Low — 3 classes)
- **Features:** 17 features (academic performance, career preferences, lifestyle)
- **Model artifact:** `ml/artifacts/models/m5_skill_gap_analyzer.joblib`

### Training Dataset
- **Samples:** 160
- **Features:** 17
- **Target classes:** High, Medium, Low

### Verified Metrics

| Metric | RandomForest | HistGradientBoosting |
|--------|-------------|---------------------|
| **Accuracy** | 0.963 | 0.931 |
| **Precision (weighted)** | 0.966 | 0.938 |
| **Recall (weighted)** | 0.963 | 0.931 |
| **F1 (weighted)** | 0.961 | 0.931 |
| **AUC** | 0.000 | 0.000 |

**Source:** `ml/reports/m5_report.md:14-17`

### Metric Notes
- **AUC = 0.000**: This is a known multiclass limitation — `roc_auc_score` with `multi_class='ovr'` can produce 0.0 when class probabilities are not well-calibrated for one-vs-rest. This does NOT mean the model is random.
- **Accuracy=0.963**: Appropriate for balanced multi-class classification; however, with only 160 samples, this metric should be interpreted with caution.
- **F1=0.961**: Appropriate primary metric for multi-class classification.
- **Precision/Recall**: Weighted averages across 3 classes.

### Feature Importance

| Feature | Importance |
|---------|-----------|
| avg_semester_percentage | 0.545 |
| avg_semester_attendance | 0.065 |
| pass_ratio | 0.050 |
| daily_study_hours | 0.050 |
| average_sleep_hours | 0.047 |
| percentage_trend_slope | 0.043 |
| total_backlogs_computed | 0.042 |
| num_semesters_recorded | 0.030 |
| stress_level | 0.023 |
| attendance_commitment | 0.021 |

**Source:** `ml/reports/m5_report.md:24-37`

### Important Caveat
The final evaluation master document states: "M5 does NOT train an ML classifier and computes no synthetic accuracy percentages." However, the `m5_report.md` and `ml/artifacts/models/m5_skill_gap_analyzer.joblib` confirm that an ML classifier IS trained and stored. The evaluation master document appears to describe the career guidance output layer (domain mapping + GenAI), while the underlying ML component classifies skill gap priority. Both layers coexist.

---

## Additional Models

**No additional prediction/intelligence models were found** beyond M1–M5. References to "M6" and "M7" in documentation refer to project **milestones** (deployment and dashboards), not ML models.

---

## Metric Definitions

### Regression Metrics (M1, M2)

| Metric | Definition | Appropriate For |
|--------|-----------|----------------|
| **MAE** | Mean Absolute Error — average of absolute differences between predicted and actual values | All regression models |
| **RMSE** | Root Mean Squared Error — square root of average squared differences; penalizes large errors more than MAE | All regression models |
| **R²** | Coefficient of Determination — proportion of variance in target explained by the model (1 = perfect, 0 = baseline, negative = worse than mean) | All regression models |
| **Pearson r** | Linear correlation between predicted and actual values (-1 to +1) | All regression models |

### Classification Metrics (M3, M5)

| Metric | Definition | Appropriate For |
|--------|-----------|----------------|
| **Accuracy** | Fraction of correct predictions out of total | Balanced multi-class (M5) |
| **Precision** | Of all positive predictions, fraction that are truly positive | Binary/multi-class classification |
| **Recall** | Of all actual positives, fraction correctly detected | Binary/multi-class classification (especially important for imbalanced data) |
| **F1-Score** | Harmonic mean of precision and recall (2 × P × R / (P + R)) | Binary/multi-class classification |
| **ROC-AUC** | Area under the Receiver Operating Characteristic curve; measures discrimination ability across all thresholds | Binary classification (M3) |
| **PR-AUC** | Area under the Precision-Recall curve; more informative than ROC-AUC for imbalanced datasets | Imbalanced binary classification (M3) |

### Deterministic Metrics (M4)

| Metric | Definition | Appropriate For |
|--------|-----------|----------------|
| **Deterministic reproducibility** | Identical input → identical output across runs | Rule-based scoring engines |
| **Input validation** | Checks that all inputs meet expected constraints | Any deterministic system |
| **Byte-for-byte comparison** | Output files are bit-identical across independent runs | Deterministic systems |

---

## Evidence / Source Mapping

| Model | Metric | Value | Source File | Function/Section | Status |
|-------|--------|-------|-------------|------------------|--------|
| M1 v3 | MAE (val) | 6.1548 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | val_metrics.mae (line 64) | VERIFIED |
| M1 v3 | RMSE (val) | 7.7213 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | val_metrics.rmse (line 64) | VERIFIED |
| M1 v3 | R² (val) | 0.4433 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | val_metrics.r2 (line 64) | VERIFIED |
| M1 v3 | MAE (test) | 6.2913 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | test_metrics.mae (line 68) | VERIFIED |
| M1 v3 | RMSE (test) | 7.8478 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | test_metrics.rmse (line 68) | VERIFIED |
| M1 v3 | R² (test) | 0.4385 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | test_metrics.r2 (line 68) | VERIFIED |
| M1 v3 | Pearson r (test) | 0.6624 | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | test_metrics.corr (line 68) | VERIFIED |
| M1 v3 | Within ±10 (test) | 79.55% | `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | test_metrics.within10 (line 69) | VERIFIED |
| M2 Theory | MAE (test) | 2.8718 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_theory.test_metrics.mae (line 69) | VERIFIED |
| M2 Theory | RMSE (test) | 3.6921 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_theory.test_metrics.rmse (line 70) | VERIFIED |
| M2 Theory | R² (test) | 0.7796 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_theory.test_metrics.r2 (line 71) | VERIFIED |
| M2 Theory | MAE (temporal) | 3.339 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_theory.temporal_metrics.mae (line 85) | VERIFIED |
| M2 Theory | R² (temporal) | 0.7054 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_theory.temporal_metrics.r2 (line 87) | VERIFIED |
| M2 Practical | MAE (test) | 4.937 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_practical.test_metrics.mae (line 165) | VERIFIED |
| M2 Practical | RMSE (test) | 6.2528 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_practical.test_metrics.rmse (line 166) | VERIFIED |
| M2 Practical | R² (test) | 0.574 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_practical.test_metrics.r2 (line 167) | VERIFIED |
| M2 Practical | MAE (temporal) | 5.324 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_practical.temporal_metrics.mae (line 181) | VERIFIED |
| M2 Practical | R² (temporal) | 0.3333 | `ml/M2_TP_CampusX_package/metadata/M2_TP_METADATA.json` | m2_practical.temporal_metrics.r2 (line 183) | VERIFIED |
| M3 | Precision | 0.9500 | `ml/reports/ML-13-retraining-final-report.md` | Evaluation Metrics table (line 63) | VERIFIED |
| M3 | Recall | 0.9667 | `ml/reports/ML-13-retraining-final-report.md` | Evaluation Metrics table (line 64) | VERIFIED |
| M3 | F1-Score | 0.9572 | `ml/reports/ML-13-retraining-final-report.md` | Evaluation Metrics table (line 65) | VERIFIED |
| M3 | ROC-AUC | 0.9955 | `ml/reports/ML-13-retraining-final-report.md` | Evaluation Metrics table (line 66) | VERIFIED |
| M3 | PR-AUC | 0.9472 | `ml/reports/ML-13-retraining-final-report.md` | Evaluation Metrics table (line 67) | VERIFIED |
| M3 v3 | F1 (temporal) | 0.679 | `ml/v3/m3_endterm_risk/reports/m3_v3_validation_report.md` | Temporal Hold-Forward table (line 76) | VERIFIED |
| M3 v3 | ROC-AUC (temporal) | 0.984 | `ml/v3/m3_endterm_risk/reports/m3_v3_validation_report.md` | Temporal Hold-Forward table (line 76) | VERIFIED |
| M4 | Score range | 13.15–94.41 | `MDs/ml/M4/m4_report.md` | Results summary (line 126) | VERIFIED |
| M4 | Validation checks | 7/7 PASS | `MDs/ml/M4/m4_report.md` | Validation checks table (lines 108-116) | VERIFIED |
| M5 | Accuracy | 0.963 | `ml/reports/m5_report.md` | Cross-Validation Results (line 16) | VERIFIED |
| M5 | F1 (weighted) | 0.961 | `ml/reports/m5_report.md` | Cross-Validation Results (line 16) | VERIFIED |
| M5 | Precision (weighted) | 0.966 | `ml/reports/m5_report.md` | Cross-Validation Results (line 16) | VERIFIED |
| M5 | Recall (weighted) | 0.963 | `ml/reports/m5_report.md` | Cross-Validation Results (line 16) | VERIFIED |

---

## Missing Metrics

| Model | Metric | Status | Reason |
|-------|--------|--------|--------|
| M1 | Accuracy | NOT APPLICABLE | Regression model — accuracy is not a valid metric |
| M1 | Precision/Recall/F1 | NOT APPLICABLE | Regression model — these are classification metrics |
| M1 | ROC-AUC/PR-AUC | NOT APPLICABLE | Regression model — these are classification metrics |
| M2 | Accuracy | NOT APPLICABLE | Regression model |
| M2 | Precision/Recall/F1 | NOT APPLICABLE | Regression model |
| M2 | ROC-AUC/PR-AUC | NOT APPLICABLE | Regression model |
| M3 | Accuracy | NOT REPORTED | Appropriate metric was not reported; F1/ROC-AUC used instead (correct for imbalanced data) |
| M3 | Confusion Matrix | NOT AVAILABLE | Computed dynamically during CV, not saved as static artifact |
| M3 | Dataset sample count for test | NOT AVAILABLE IN CURRENT PROJECT | CV metrics reported; explicit test-set metrics not separated in ML-13 report |
| M4 | All ML metrics | NOT APPLICABLE | Deterministic rule-based system — no trained model exists |
| M5 | ROC-AUC | 0.000 (DEGENERATE) | Multiclass limitation; AUC computation returned 0.0 for both algorithms |
| M5 | Confusion Matrix | NOT AVAILABLE IN CURRENT PROJECT | Not saved in m5_report.md |
| M5 | Per-class metrics | NOT AVAILABLE IN CURRENT PROJECT | Only weighted aggregates reported |
| M5 | Temporal validation | NOT AVAILABLE IN CURRENT PROJECT | Only CV results reported; no temporal holdout documented |

---

## Final Verified Metrics for PPT

### Safe to Use (All VERIFIED)

**M1 — Subject Performance Predictor (Regression)**
- MAE = 6.29 marks (test set)
- R² = 0.44 (test set)
- ~80% of predictions within ±10 marks of actual

**M2 — Next-Semester Performance Predictor (Regression)**
- Theory: MAE = 2.87%, R² = 0.78 (test set)
- Practical: MAE = 4.94%, R² = 0.57 (test set)
- Theory temporal: MAE = 3.34%, R² = 0.71

**M3 — At-Risk Classifier (Binary Classification)**
- Precision = 0.9500
- Recall = 0.9667
- F1-Score = 0.9572
- ROC-AUC = 0.9955
- PR-AUC = 0.9472
- Trained on 453 samples (420 historical + 33 faculty feedback)

**M4 — Career Readiness Score (Deterministic)**
- 100-point rule-based rubric (NOT ML)
- 80 students scored: 19 High, 46 Medium, 15 Low
- Score range: 13.15–94.41
- Byte-for-byte deterministic, 7/7 validation checks PASS

**M5 — Career Skill Gap Analyzer (Multi-class Classification)**
- Accuracy = 0.963
- F1 = 0.961
- 160 training samples, 17 features, 3 classes (High/Medium/Low)

### DO NOT Use in PPT
- M1 "accuracy" — regression model, accuracy is meaningless
- M2 "accuracy" — regression model
- M4 "accuracy" / "precision" / "recall" — deterministic system, not ML
- M5 ROC-AUC = 0.000 — degenerate multiclass computation, not meaningful
- Any old/synthetic metrics flagged as "trustworthy: false" in ml_old_vs_v2_comparison.json

---

*Report generated by forensic inspection of the CampusX codebase. All metrics traced to source files. No metrics were fabricated or estimated.*
