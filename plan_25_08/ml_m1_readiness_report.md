# M1 — Prediction-Readiness Assessment Report

## 1. Objective
Determine whether the persisted M1 artifact
(`ml/artifacts/models/m1_subject_endmarks.joblib`, selected model
`hist_gbm`) is **technically ready for offline inference/scoring** under the
existing project contract — and nothing more. This is a read-only assessment:
**no retraining, no model selection change, no artifact/DB/ETL/schema/API/
dashboard/GenAI/authentication changes, and no student-facing prediction.**

Scope boundary is explicit: this report approves **offline scoring only**.
Approval for production, API, dashboard, or student-facing prediction is a
separate (future/M4) step and is NOT granted here.

## 2. Existing inference contract (reused verbatim)
- **Target:** `end_sem_marks` (0–70), grain `(student_id, subject_id, semester_no)`.
- **Feature contract:** 8 raw → 12 encoded columns (`internal_marks`,
  `mid_sem_marks`, `attendance_percentage`, `credits`, `semester_no`,
  4× `subject_type_*`, 2× `department_name_*`, `is_male`).
- **Artifact structure:** `{model, preprocess, feature_names, feature_tier,
  metadata}`; `preprocess == []` (no fitted scaler/imputer to apply).
- **Clipping:** predictions clipped to `[0,70]`.
- **Inference path:** `InferenceService.predict_m1` (inference.py) +
  `features.prepare_m1_inference` / `build_m1_features` (features.py) — the
  authoritative feature prep. Reused directly, not rebuilt.
- **Loader:** `registry.load_model("m1")` (ML-01) — safe, validated loading.
- **Selected model remains:** HistGradientBoostingRegressor (unchanged).

## 3. Temporal boundary (respected)
- **Historical labeled rows** (semesters 1–6 with a true `end_sem_marks`) →
  used for the readiness metrics (MAE/RMSE/R²). Real labels only.
- **Semester 7 = deployment boundary** → reported separately; its target is
  unavailable and is **never** used to fabricate a metric.
- **Deployment rows** (`end_sem_marks IS NULL`, 557 rows: sem-5 × 210, sem-7
  × 347) → inference-only; only a prediction distribution is reported.

## 4. Methodology
`m1/readiness.run_readiness` loads real raw CSV tables
(`data.load_tables`) and the artifact, then:
1. Builds features via the existing `prepare_m1_inference` (exact inference prep).
2. Predicts with the stored model and clips to `[0,70]`.
3. Splits rows by temporal boundary (labeled-eval vs deployment vs sem-7).
4. Computes MAE/RMSE/R² only on historical labeled rows.
5. Runs the inference path a second time to confirm determinism.
6. Captures the artifact SHA-256 + mtime before/after to prove no writes.

## 5. Results (live verification: `verify_m1_readiness.py`, PASS)

| Item | Value |
|---|---|
| Artifact SHA-256 | `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E` |
| Artifact mtime | 2026-08-12T23:24:44.893803 (unchanged) |
| Model type | HistGradientBoostingRegressor |
| Features | 12 (contract compatible: True) |
| Total fact rows | 3850 |
| Labeled eval rows (sem 1–6) | 3290 |
| Deployment rows (target NULL) | 557 |
| Semester-7 boundary rows | 350 (3 labeled @ sem 7 + 347 deploy) |

**Readiness metrics — historical labeled rows (RESUBSTITUTION / in-sample):**

| Metric | Value |
|---|---|
| MAE | 2.7157 |
| RMSE | 3.2171 |
| R² | 0.8930 |
| n | 3290 |

Per-semester MAE (labeled rows): sem1 2.703 / sem2 2.743 / sem3 2.753 /
sem4 2.778 / sem5 2.697 / sem6 2.555.

**Deployment rows (inference-only, NO metric):**
predictions min/mean/max = 21.8 / 50.61 / 68.1 (n=557), clipped to `[0,70]`.

## 6. Reproduction / diagnostics
| Check | Result |
|---|---|
| Artifact loads (dict, valid shape) | ✅ |
| 12-feature contract compatible | ✅ |
| Prediction shape == row count | ✅ |
| Predictions finite (no NaN/inf) | ✅ |
| Predictions within `[0,70]` | ✅ |
| Deterministic (2 runs identical) | ✅ |
| Eval uses only true labels | ✅ |
| Deployment rows excluded from eval | ✅ |
| Sem-7 boundary reported separately | ✅ |
| Artifact hash/mtime UNCHANGED | ✅ |

**Determinism/RANDOM_STATE:** the readiness check is deterministic (fixed
artifact, deterministic feature prep, no sampling); it was run twice with
identical results. The artifact's SHA-256 was verified unchanged after the
assessment (read-only; no retraining).

## 7. Verdict
**READY for offline inference/scoring.** The persisted artifact loads cleanly,
is feature-compatible with the existing 12-feature contract, produces
finite/in-range/deterministic predictions, and yields a meaningful historical
label MAE (2.72). **Not approved** here for production/API/dashboard/
student-facing prediction.

## 8. Honest limitations (README-visible)
- The readiness MAE/RMSE/R² are **resubstitution (in-sample)** estimates: the
  model was trained on these labeled rows, so they validate that the persisted
  artifact *runs correctly and reproduces training quality* — they are **not**
  held-out generalization.
- **Held-out temporal generalization** is measured independently by the M1
  multi-holdout temporal validation (hist_gbm mean MAE ≈ 3.23 ± 0.12,
  RMSE 3.87 ± 0.19, R² 0.84 ± 0.01 across validation semesters 2–6). Use that
  for expected out-of-sample error, not the resubstitution numbers above.
- No deployment target was fabricated; deployment metrics cannot be stated.
- Full-suite coverage: **551 tests passed** (prior 533 + 18 new
  `test_m1_readiness`); no regressions.

## 9. Files added (read-only assessment, no model/artifact writes)
- `ml/src/m1/readiness.py` — readiness module (reuses features/registry/config).
- `ml/tests/test_m1_readiness.py` — 18 focused tests.
- `ml/verify_m1_readiness.py` — live verification script (PASS).
- `plan_25_08/ml_m1_readiness_report.md` — this report.

Stopping here. The M1 prediction-readiness step is complete; no M4/deployment/
API/dashboard/ETL/DB/GenAI work was performed.
