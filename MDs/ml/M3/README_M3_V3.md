# M3 v3 — Same-Semester End-Term Academic Risk Prediction

Production-ready machine learning package for predicting same-semester end-term academic risk from mid-semester performance signals.

---

## 1. Overview & Business Objective

M3 v3 predicts whether an undergraduate student will enter an academic-risk state (failing $\ge 1$ subject or receiving an ATKT backlog) at the end of the **same academic semester**, evaluated immediately after mid-semester exams:
* **CSE Cohort**: Semester 7 Mid-Sem $\rightarrow$ Semester 7 End-Term
* **BBA Cohort**: Semester 5 Mid-Sem $\rightarrow$ Semester 5 End-Term

### Distinction from Other M3 Versions
* **M3 v1**: Legacy next-semester model (`/predict/m3/`), permanently **BLOCKED** from production.
* **M3 v2**: Cross-semester progression model (`/predict/m3v2/`), predicting transition risk from completed semester $T$ into upcoming semester $T+1$.
* **M3 v3 (This Model)**: Same-semester early warning model (`/predict/m3v3/`), predicting risk in semester $T$'s final exams using mid-semester $T$ signals.

---

## 2. Directory Structure

```
ml/v3/m3_endterm_risk/
├── artifacts/
│   └── models/
│       └── m3_v3_endterm_risk.joblib   # Validated production model artifact
├── config.py                           # Configurations, feature tiers, and forbidden list
├── data/
│   └── loader.py                       # Cohort data loading and DB extraction
├── features/
│   ├── builder.py                      # Feature engineering & mid-sem aggregations
│   └── leakage_gate.py                 # Fail-closed automated feature leakage gate
├── preprocessing/
│   └── pipeline.py                     # M3V3Preprocessor & feature selection
├── inference/
│   └── predictor.py                    # Inference engine (M3V3Predictor)
├── training/
│   └── train.py                        # Model training, calibration, and artifact generation
├── validation/
│   └── cv.py                           # GroupKFold & temporal holdout validation
├── tests/
│   └── test_m3_v3.py                   # Pytest test suite (40 unit & integration tests)
├── reports/
│   └── m3_v3_validation_report.md      # Validation and audit report
├── FEATURE_CONTRACT.md                 # 27-feature contract specification
├── MODEL_CARD.md                       # Comprehensive model card & governance documentation
└── README.md                           # This file
```

---

## 3. Quickstart & Usage

### A. Python Inference
```python
import asyncpg
from v3.m3_endterm_risk.inference.predictor import get_predictor

# Load predictor singleton
predictor = get_predictor()

# Run prediction using an existing asyncpg DB connection
async def evaluate_student(student_id: str, pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        result = await predictor.predict_for_student(student_id, conn)
    print(f"Risk Probability: {result['probability_at_risk']}")
    print(f"At Risk Flag: {result['is_estimated_at_risk']}")
    return result
```

### B. FastAPI Endpoint
The model is exposed via the read-only FastAPI endpoint:
```http
GET /api/v1/predict/m3v3/{student_id}
```
**Access Control (RBAC)**:
* **Student**: May only access their own `student_id`.
* **Faculty**: May only access students in their assigned department or mentee scope.
* **Admin**: Unrestricted access.

**Response Schema (`200 OK`)**:
```json
{
  "student_id": "STU6A0001",
  "model_id": "m3",
  "model_version": "3.0",
  "readiness_status": "READY",
  "observation_semester": 6,
  "prediction_point": "MID_SEM",
  "prediction_target_semester": 6,
  "prediction_scope": "Computer Science and Engineering Semester 6 Mid-Sem → End-Term",
  "probability_at_risk": 0.0421,
  "threshold": 0.33,
  "is_estimated_at_risk": false,
  "signals": [
    {
      "feature": "subj_mid_sem_marks_mean",
      "raw_value": 34.0,
      "importance": 0.284
    }
  ],
  "note": "End-term risk estimate based on mid-semester performance. This is a model estimate, not a certainty."
}
```

---

## 4. Key Metrics & Validation Highlights

* **Algorithm**: `HistGradientBoostingClassifier` with balanced class weights
* **Tuned Threshold**: `0.330`
* **Performance on Semester 7 Temporal Holdout (1,200 students)**:
  * **F1 Score**: `0.655` (vs. 0.000 for majority and prior backlog baselines)
  * **Recall**: `67.9%`
  * **Precision**: `63.3%`
  * **ROC-AUC**: `0.984`
  * **PR-AUC**: `0.696`

---

## 5. Running Tests

Run ML unit and leakage tests:
```bash
python -m pytest ml/v3/m3_endterm_risk/tests/test_m3_v3.py -v
```

Run backend endpoint and RBAC integration tests:
```bash
python -m pytest backend/tests/test_m3_v3_prediction.py -v
```

Run both test suites together:
```bash
python -m pytest ml/v3/m3_endterm_risk/tests/test_m3_v3.py backend/tests/test_m3_v3_prediction.py -v
```
