# CampusX ML Model Inventory (M1–M5)

**Audit date:** 2026-09-07
**Scope:** All prediction/analytics models referenced by the CampusX application (frontend, backend APIs, chatbot, admin/faculty tools).
**Method:** Static code trace + direct artifact inspection (`joblib` introspection with `ml/` on `sys.path`). No source code was modified.

## Summary Table

| Model | Name / Artifact | Kind | Target | Features | Status | Served via |
|---|---|---|---|---|---|---|
| M1 (v1 legacy) | `ml/artifacts/models/m1_subject_endmarks.joblib` | Supervised ML (HistGradientBoostingRegressor) | `end_sem_marks` [0,70] | 12 (8 raw → OHE) | READY (legacy) | `GET /predict/m1/{student_id}` |
| M1 V2 | `ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib` | Supervised ML (Ridge) | `end_sem_marks` [0,70] | 39 | READY (production) | `GET /predict/m1v2/{student_id}` |
| M1 V3 (clean) | `ml/M1_v3_CampusX_package/model/m1_v3_pipeline.pkl` (`m1_v3_clean`) | Supervised ML (HistGradientBoostingRegressor) | `end_sem_marks` [0,70] | 38 | READY (production) | `GET /predict/m1v3/{student_id}` |
| (M1 V3 synthetic, removed) | `ml/v3/m1_subject_prediction/artifacts/m1_synthetic_v1.joblib` | Supervised ML (LinearRegression) | `end_sem_marks` [0,70] | 8 | **REMOVED** 2026-09-07 | replaced by `m1_v3_clean` |
| M2 (v1 legacy) | `ml/artifacts/models/m2_next_semester_performance.joblib` | Supervised ML (2× `Pipeline`, sklearn) | `next_semester_sgpa`, `next_semester_percentage` | 10 raw | READY (legacy) | `GET /predict/m2/{student_id}` |
| M2 V2 | `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib` | Supervised ML (RF for sgpa, Ridge for pct) | `next_semester_sgpa`, `next_semester_percentage` | 34 | READY (production) | `GET /predict/m2v2/{student_id}` |
| M3 (v1 legacy) | `ml/artifacts/models/m3_next_semester_at_risk.joblib` | Supervised ML (`Pipeline`, classifier) | `is_at_risk_next_sem` (binary) | — | **BLOCKED** (never served) | `GET /predict/m3/{student_id}` → BLOCKED |
| M3 V2 | `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` | Supervised ML (RandomForestClassifier) | `is_at_risk_next_sem` (binary) | 35 | READY (production) | `GET /predict/m3v2/{student_id}` |
| M4 | (no artifact — deterministic engine) | **Rule-based** (`CareerReadinessEngine`, ml/src/m4/engine.py) | `career_readiness_score` 0–100 + level | — | READY (deterministic, version 1.0) | `GET /predict/m4/{student_id}` |
| M5 | (no artifact holistically) | **Controlled mapping + notified GenAI reasoning** (no trained classifier) | Domain / skill-gap / roadmap guidance | — | Active (Student-only) | `GET /student/me/career/guidance`, career coach tool |

---

## Key facts per model

### M1 subject end-marks regression (3 variants)
- v1 legacy: trained on **synthetic** 80-student data (3,293 train / 557 deploy rows); `hist_gbm`; CV MAE≈3.18, R²≈0.817. Explicit `feature_tier` and `stage_a/stage_b` metadata present. **Metrics untrustworthy** (near-stationary synthetic correlations 0.86–0.99).
- V2: trained on **real** 1,200-student CSE 6A cohort (58,800 rows), cohort guard `STU6A`, 39-feature contract, `ridge`. Honest CV MAE≈6.319, R²≈0.434; temporal holdout MAE≈6.302. This is the **production** M1.
- V3 (clean, replaces synthetic): HistGradientBoostingRegressor, 38-feature `C_core_history_learning` contract, packaged at `ml/M1_v3_CampusX_package` with production adapter `ml/v3/m1_subject_prediction_clean/inference/predictor.py`; honest test MAE≈6.29, R²≈0.44 (real-data temporal holdout). Served at the same `/predict/m1v3` endpoint. The synthetic 8-feature LinearRegression V3 was removed.

### M2 next-semester performance
- v1 legacy: two sklearn Pipelines (`next_semester_sgpa`, `next_semester_percentage`), no metadata dict (plain dict of pipelines).
- V2: single dict with `models` (RF/Ridge), 34 features, cohort `STU6A`.

### M3 at-risk (T→T+1)
- v1 legacy: sklearn `Pipeline`; **not approved** — unified contract forces `readiness_status=BLOCKED`, `prediction_available=False`; route hard-rejects any non-BLOCKED result.
- V2: RandomForestClassifier, 35 features, tuned threshold, `is_at_risk_next_sem` binary. `M3V2PredictionService` returns probability + top signals.

### M4 career readiness (deterministic)
- `CareerReadinessEngine.calculate` weights: `academic_performance=35`, `growth_trend=10`, `career_preparedness=25`, `lifestyle_discipline=30`; level thresholds `High≥75`, `Medium≥50`. **Explicitly rule-based, not ML** — same provenance as the chatbot's M4 disclaimer.

### M5 career guidance (controlled reasoning)
- No trained model. Reuses `student_career_rules.DOMAIN_SUBJECT_KEYWORDS` + inference-only `_SUBJECT_SKILL_LABELS`; optional grounded GenAI narrative through the existing **G0 boundary**. M4 output is reused as evidence, never recomputed.

---

## Artifact inventory (verify-all)

| Artifact | Size | Last modified |
|---|---|---|
| `ml/artifacts/models/m1_subject_endmarks.joblib` | 441,234 B | 2026-08-12 |
| `ml/artifacts/models/m2_next_semester_performance.joblib` | 570,857 B | 2026-08-28 |
| `ml/artifacts/models/m3_next_semester_at_risk.joblib` | 2,081 B | 2026-08-14 |
| `ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib` | 6,903 B | 2026-08-31 |
| `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib` | 7,659,768 B | 2026-09-01 |
| `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` | 1,690,232 B | 2026-09-01 |
| `ml/M1_v3_CampusX_package/model/m1_v3_pipeline.pkl` | packaged sklearn Pipeline | 2026-09-07 |

No `.pkl`/`joblib` artifacts exist for M4/M5 (no artifact required).

---

## Classification (ML vs non-ML)

- **TRUE trained ML models:** M1 v1, M1 V2, M1 V3 (clean), M2 v1, M2 V2, M3 v1, M3 V2. The synthetic M1 V3 was removed 2026-09-07.
- **Deterministic rule-based (NOT ML):** M4 (CareerReadinessEngine). This is the security-hard dependency — never call it "an ML model".
- **Controlled mapping + GenAI reasoning (NOT a classifier):** M5 (career coach). No training, no accuracy/confidence, no placement probability. Optional GenAI narrative is grounded by the G0 verified-context boundary and fails closed.
- **BLOCKED model:** M3 v1 legacy — exists as an artifact, never served live; route-level enforcement prevents production exposure.