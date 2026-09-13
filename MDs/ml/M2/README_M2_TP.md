# M2-TP: Next-Semester Theory & Practical Performance Prediction

**Package Version**: 1.0.0 (Clean Isolated Experiment)  
**Dataset Source**: 27-table export (`supabase_export_04_09_latest_27table`)  
**Experiment Date**: 2026-09-08  

---

## 1. Executive Summary

The **M2-TP** experiment develops two separate, contract-compliant regression models to predict next-semester academic performance split strictly by pedagogical delivery mode:
1. **`M2_T`**: Next-Semester **Theory** Performance Percentage ($0 - 100\%$)
2. **`M2_P`**: Next-Semester **Practical / Laboratory** Performance Percentage ($0 - 100\%$)

Both models predict expected student performance in regular academic semester $S$ using **only** information available prior to semester $S$. Theory and Practical historical performance signals are kept strictly isolated.

---

## 2. Dataset & Subject Classification

From `subjects.csv`:
- **Theory Subjects** (`subject_type == 'Theory'`): 78 catalog subjects (all standard 3 credits).
- **Practical / Laboratory Subjects** (`subject_type == 'Laboratory'`): 13 catalog subjects (all standard 2 credits).
- **Projects** (4 credits) and **Internships** (12 credits) are excluded from Theory and Practical targets.

From `student_subject_performance.csv`:
- Total completed subject performance records: **71,691**
- Theory completed records: **54,281**
- Laboratory completed records: **13,680**

### Next-Semester Dataset Sample Counts:
- **`M2_T` Dataset**: **7,541 samples** across 1,280 distinct students (Semesters 2 to 7).
- **`M2_P` Dataset**: **6,230 samples** across 1,280 distinct students (Semesters 2 to 7). Note: Semester 2 only has 30 lab targets because only BBA students take a lab course in Sem 2. Sem 8 consists exclusively of full-time internship (0 Theory, 0 Lab).

---

## 3. Target Definitions

1. **`target_theory_pct`**: Arithmetic mean of the final subject percentages across all Theory courses in target semester $S$.
2. **`target_lab_pct`**: Arithmetic mean of the final subject percentages across all Laboratory courses in target semester $S$.

---

## 4. Algorithms Evaluated & Model Selection

Per Rule 7 of `GLOBAL_ML_RULE`, exactly 3 candidate algorithms were evaluated:
1. **Ridge Regression** (`Ridge(alpha=10.0)`)
2. **Random Forest** (`RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_leaf=4)`)
3. **HistGradientBoostingRegressor** (`HistGradientBoostingRegressor(max_iter=150, max_depth=6)`)

### A. M2_T (Theory Performance) Algorithm Comparison on Validation Set (192 Students, 1,129 Rows):

| Algorithm | MAE | RMSE | $R^2$ | Pearson $r$ | Within $\pm 5\%$ | Within $\pm 10\%$ | Weak MAE ($<60\%$) | Selected |
|---|---|---|---|---|---|---|---|---|
| **Random Forest** | **2.9029** | **3.7412** | **0.7828** | **0.8858** | 83.26% | 98.49% | 5.7233 | **YES** |
| Ridge Regression | 2.9648 | 3.7626 | 0.7803 | 0.8842 | 83.70% | 98.76% | 5.8903 | No |
| HistGradientBoosting | 2.9425 | 3.7978 | 0.7761 | 0.8817 | 83.08% | 98.32% | 5.6464 | No |

### B. M2_P (Practical Performance) Algorithm Comparison on Validation Set (192 Students, 933 Rows):

| Algorithm | MAE | RMSE | $R^2$ | Pearson $r$ | Within $\pm 5\%$ | Within $\pm 10\%$ | Weak MAE ($<60\%$) | Selected |
|---|---|---|---|---|---|---|---|---|
| **Ridge Regression** | **4.9133** | **6.4179** | **0.5168** | **0.7198** | **60.45%** | **88.42%** | 14.5627 | **YES** |
| Random Forest | 4.9405 | 6.4567 | 0.5109 | 0.7155 | 60.02% | 88.21% | 14.2842 | No |
| HistGradientBoosting | 5.0693 | 6.5980 | 0.4893 | 0.7013 | 59.16% | 87.46% | 13.9921 | No |

---

## 5. Final Evaluation Metrics

### A. Untouched Test Set Evaluation (192 Held-Out Students, Evaluated Once):

| Metric | M2_T (Random Forest) | M2_P (Ridge Regression) |
|---|---|---|
| **Test Sample Size** | 1,143 samples | 949 samples |
| **MAE** | **2.8718 percentage points** | **4.9370 percentage points** |
| **RMSE** | **3.6921** | **6.2528** |
| **$R^2$ Score** | **0.7796** | **0.5740** |
| **Pearson Correlation ($r$)** | **0.8831** | **0.7588** |
| **Within $\pm 5\%$ Accuracy** | **84.51%** | **59.33%** |
| **Within $\pm 10\%$ Accuracy** | **99.48%** | **90.09%** |
| **Within $\pm 15\%$ Accuracy** | **99.91%** | **97.58%** |

### B. Temporal Robustness Evaluation (Trained on Sem $\le 5$, Tested on Sem $6 \& 7$):

| Metric | M2_T (Temporal Test) | M2_P (Temporal Test) |
|---|---|---|
| **Temporal Test Samples** | 2,451 samples | 2,450 samples |
| **MAE** | **3.3390 percentage points** | **5.3240 percentage points** |
| **RMSE** | **4.2489** | **6.7893** |
| **$R^2$ Score** | **0.7054** | **0.3333** |
| **Pearson Correlation ($r$)** | **0.8487** | **0.7508** |
| **Within $\pm 5\%$ Accuracy** | **77.15%** | **57.10%** |
| **Within $\pm 10\%$ Accuracy** | **97.92%** | **86.04%** |
| **Within $\pm 15\%$ Accuracy** | **99.96%** | **96.65%** |

---

## 6. Performance Insights & Regression-to-the-Mean Analysis

1. **Predictive Granularity**:
   - Theory performance has lower error ($\approx 2.87\%$ MAE) because each semester aggregates 4 to 8 theory subjects, smoothing out idiosyncratic course variations.
   - Practical performance has higher variance ($\approx 4.94\%$ MAE) because practical grades depend on smaller subject counts (1 to 3 labs) with varying lab instructor criteria.
2. **Regression-to-the-Mean Slope**:
   - `M2_T`: $0.762$, indicating healthy responsiveness across the performance spectrum without over-compressing to cohort average.
   - `M2_P`: $0.521$, showing moderate shrinkage towards the practical baseline ($77.2\%$), preventing runaway extreme predictions.

---

## 7. Artifact Directory Structure

```
M2_TP_CampusX_package/
├── model/
│   ├── m2_theory_pipeline.pkl          # Self-contained RandomForest pipeline
│   └── m2_practical_pipeline.pkl       # Self-contained Ridge pipeline
├── inference/
│   └── m2_tp_predict.py                # Deterministic inference engine
├── schema/
│   ├── theory_features.json            # 32-feature contract schema
│   ├── practical_features.json         # 33-feature contract schema
│   └── M2_TP_FEATURE_CONTRACT.md       # Full documentation of feature lineage
├── metadata/
│   ├── M2_TP_METADATA.json             # Complete experiment run records
│   └── model_sha256.txt                # Cryptographic checksums
├── src/
│   ├── dataset_builder.py              # Stitches 27 CSV tables, enforces temporal cutoff
│   ├── train_m2_tp.py                  # 3-algo comparison, evaluation, and artifact export
│   └── smoke_test.py                   # Automated reload & precision smoke tests
├── README.md                           # This document
└── requirements.txt                    # Minimal environment requirements
```

---

## 8. Model Checksums (SHA-256)

- **`m2_theory_pipeline.pkl`**:
  `de13eb0c868fceab4f2b188c84106bd99493f02f56c486dde1ac95408b9fe804`
- **`m2_practical_pipeline.pkl`**:
  `4e04f07c3d4580b8b3589e69340dec18eeb06ad867fa54ed541472181ed17f39`

---

## 9. Quickstart / Inference Usage

```python
from inference.m2_tp_predict import M2TPPredictor

predictor = M2TPPredictor()

# Input dictionary conforming to M2_TP_FEATURE_CONTRACT.md
student_input = {
    "target_semester_no": 6,
    "department_code": 1,
    "gender": "Female",
    "category": "General",
    "admission_year": 2022,
    "prev_completed_semesters": 5,
    "prev_overall_sgpa_mean": 8.12,
    "prev_overall_pct_mean": 75.40,
    "prev_overall_attendance_mean": 84.50,
    "prev_cumulative_backlogs": 0.0,
    "latest_sem_sgpa": 8.25,
    "latest_sem_pct": 76.10,
    "latest_sem_attendance": 86.00,
    "target_sem_total_credits": 22.0,
    # Theory features
    "prev_theory_pct_mean": 74.80,
    "prev_theory_pct_std": 5.10,
    "prev_theory_pct_min": 64.00,
    "prev_theory_pct_max": 86.00,
    "latest_sem_theory_pct": 75.50,
    "theory_pct_trend": 0.70,
    "prev_theory_internal_avg": 18.2,
    "prev_theory_midsem_avg": 36.5,
    "prev_theory_count": 30,
    "target_sem_theory_count": 4,
    # Practical features
    "prev_lab_pct_mean": 78.50,
    "prev_lab_pct_std": 4.20,
    "prev_lab_pct_min": 70.00,
    "prev_lab_pct_max": 88.00,
    "latest_sem_lab_pct": 80.00,
    "lab_pct_trend": 1.50,
    "prev_lab_internal_avg": 19.0,
    "prev_lab_midsem_avg": 38.0,
    "prev_lab_count": 7,
    "has_prior_lab_history": 1.0,
    "target_sem_lab_count": 3,
}

# Run inference
result = predictor.predict_both(student_input)
print("Predicted Theory %:", result["theory"]["predicted_theory_percentage"])
print("Predicted Practical %:", result["practical"]["predicted_practical_percentage"])
```

---

## 10. Known Data Limitations

1. **Semester 2 Practical Sparsity**:
   Only 30 students in the dataset (BBA cohort) have a practical course in Semester 2 (`Business Communication Laboratory`). CSE students have no laboratory course in Semester 2. The pipeline correctly handles this without fabricating zero targets.
2. **Semester 8 Internship Boundary**:
   Semester 8 has 0 Theory and 0 Practical courses across all cohorts (12-credit full-time internship). The inference module returns a clean `NO_DATA` status for Semester 8 targets.
3. **CSE Semester 7 In-Progress Records**:
   CSE Semester 7 records with null `end_sem_marks` represent current active academic sessions. These were excluded from targets to prevent target leakage and data fabrication.
