# M3 V2 — Missing Signal Data Fix Report

Date: 2026-09-08 · Scope: M3 V2 (at-risk) **feature-data pipeline**, display, and verification.
Constraint honored: **no retraining, no model-artifact change, no threshold change, no M1 V3 / M2‑TP change.**

## 1. Summary

The Student → ML Insights M3 V2 card showed `—` (missing) for three signals:

| Signal | Before | After |
|---|---|---|
| `attendance_aggregate_pct` | NULL | **87.35** (recovered) |
| `learn_tsem_volume_total` | NULL | still `Not available` — source data absent |
| `att_tsem_total_pct` | NULL | still `Not available` — source data absent |

Root cause: the **real cohort (STU000001…080, the currently authorized students) has no rows in the
weekly behavioral tables and NULL derived analytics columns** in `student_semester_summary`, while the
1200-student CSE 6A training cohort has complete rows. One of the three signals is **recoverable** from
data that exists (plus four more silently-NaN Tier‑1B analytics); the other two are **not** recoverable
(honestly reported, never zero-fabricated). Model input, feature set, ordering, preprocessing contract,
and threshold are unchanged.

## 2. Pipeline trace

UI → API → service → feature assembly → DB/ETL → source tables:

1. `app/student/ml-insights/page.tsx:141` → `getStudentM3V2()` → `GET /predict/m3v2/{student_id}`
   (`backend/app/api/v1/predict.py:315`, response schema `backend/app/schemas/m3v2.py`).
2. `M3V2PredictionService.predict()` (`backend/app/services/m3v2_prediction_service.py:58`) → loads the
   v2 artifact once (cached) and calls `M3V2Predictor.predict_for_student()`.
3. `M3V2Predictor.predict_for_student()` (`ml/v2/m3_at_risk_prediction/inference/predictor.py`) is the
   production feature builder: it runs five read-only SELECTs and aggregates.
4. Declared `current_semester=7`, program length 8 (`departments`) → `T=7`, target semester 8, READY.
5. Signals = top-10 features by `feature_importances_`; `raw_value` is the **feature value passed to the
   model** (after the trained preprocessor). The API/response schema pass `raw_value` through unchanged —
   nothing in the service, schema, route, or layout drops it. The display "—" was caused by data absence
   upstream, not by a drop in the service/API/frontend layer.

DB evidence (production Supabase, via the same asyncpg pool the backend uses):

| Table | STU6A (training cohort) | STU0000xx (real cohort) |
|---|---|---|
| `students` | 1,200 | 80 (current_semester 7 / 8) |
| `student_semester_summary` | 9,600 | 500 |
| `student_subject_performance` | 68,400 | 3,850 |
| `attendance_weekly` | **547,200** | **0** |
| `student_learning_activity` | **547,200** | **0** |
| `student_lifestyle_survey` | 9,600 | 0 (legacy `lifestyle_survey` has 80 rows) |

Also NULL for the real cohort: `previous_sem_sgpa`, `sgpa_drift`, `sgpa_rolling_mean_3`,
`previous_sem_backlog_count`, `backlog_change`, `cumulative_backlog_events`, `attendance_aggregate_pct`
(all 0 of 500 populated), and `pre_endsem_assessment_pct`/`assignment_score`/`quiz_avg_marks`/
`submission_delay_days` (0 of 3,850).

## 3. Root cause per signal

- **`attendance_aggregate_pct`** — a stored `student_semester_summary` column that is NULL for the whole
  real cohort. It is **recoverable**: production base data `semester_attendance_percentage` exists.
- **`att_tsem_total_pct`** (and `att_tsem_low_pct_weeks`, `att_tsem_velocity_mean`) — computed per student
  from `attendance_weekly` (`_INFER_ATTENDANCE_SQL` + `_aggregate_attendance`). **0 rows → NULL**;
  no weekly source data exists for the cohort, so this is **not recoverable**.
- **`learn_tsem_volume_total`** (and `learn_tsem_engagement_mean`, `learn_tsem_completion_mean`,
  `learn_tsem_late_mean`) — computed from `student_learning_activity`. **0 rows → NULL**; **not recoverable**.
- Also surfaced as missing: `subj_pre_endsem_pct_mean` (and assignment/quiz/delay means) — source column
  NULL for every real student; **not recoverable**.

## 4. Training-time definitions verified from training code + 6A data

Verified empirically against stored 6A rows (e.g. `STU6A0001` sem 6: drift −0.27, roll3 8.093,
att 74.07; `STU6A0500` sem 3-4: backlog_change 1 then −1, cumulative 1):

| Feature | Training definition (source) |
|---|---|
| `previous_sem_sgpa` | `semester_sgpa` shifted +1 semester (sem 1 = NULL) |
| `sgpa_drift` | `round(semester_sgpa − previous_sem_sgpa, 2)` |
| `sgpa_rolling_mean_3` | trailing-3 SGPA mean, min_periods=1, 3dp |
| `previous_sem_backlog_count` | `backlog_count` shifted, sem 1 = 0 |
| `backlog_change` | `round(backlog_count − previous_sem_backlog_count, 1)` |
| `cumulative_backlog_events` | cumsum of `backlog_count` up to T |
| `attendance_aggregate_pct` | the T-semester aggregate attendance % (stored at 3dp; equals `semester_attendance_percentage` to within 0.005 — 2dp rounded value) |
| `att_tsem_total_pct` | `100 · Σ(classes_attended)/Σ(classes_held)` over `attendance_weekly` at T |
| `learn_tsem_volume_total` | `Σ(activity_volume)` over `student_learning_activity` at T |

Consistent with `fix_supabase_dataset.fill_analytics()` and the feature builder
(`ml/v2/m3_at_risk_prediction/features/builder.py:_aggregate_attendance/_aggregate_learning`).
All stays strictly T / ≤T (point-in-time); nothing from T+1.

## 5. Feature parity table (training → production)

| Tier | Feature | Status after fix |
|---|---|---|
| 1A summary | semester_sgpa, semester_percentage, semester_total_marks, semester_attendance_percentage, backlog_count, cumulative_backlog_events, credits_*, subjects_registered | In DB ✓ (carry-forward for unfinalized T unchanged) |
| 1B prior history | previous_sem_sgpa, sgpa_rolling_mean_3 | existing completed-past fallback ✓ |
| 1B prior history | **sgpa_drift, previous_sem_backlog_count, backlog_change, cumulative_backlog_events, attendance_aggregate_pct** | **now recovered** — training-exact derivation (fill only when stored value missing) |
| 1C subject | internal/mid/end means+std, failed count | In DB ✓ |
| 1C subject | assignment/quiz/submission_delay/pre_endsem means | **missing** — source column NULL (kept NULL) |
| 1D attendance | att_tsem_total_pct, att_tsem_low_pct_weeks, att_tsem_velocity_mean | **missing** — no weekly rows (kept NULL) |
| 1E learning | learn_tsem_volume_total, engagement, completion, late | **missing** — no weekly rows (kept NULL) |
| 1F meta | is_male, semester_no, stress_ordinal, study_hours_per_week | In DB ✓ (legacy survey fallback) |

## 6. Model input vs display — determination

For the recoverable features the model had been receiving **NaN → trained-median imputation**
(`M3Preprocessor`, `SimpleImputer(strategy="median")` fitted on 6A), and the display showed the NaN as
`—`. **Both input and display were wrong** relative to the training contract. After the fix the model
receives the real derived value (parity restored) and the display resolves.

For the non-recoverable features the model **continues to receive NaN → median imputation** (the exact
training-time behavior — training itself imputes, it does not discard). That is the correct contract;
only a data-load gap could change it. Display now reads "Not available" instead of a misleading bare "—".

## 7. Missing-vs-zero rule (implemented/tested)

- `0` is returned only when it is the mathematically correct value: e.g. `att_tsem_total_pct` with real
  weekly rows and `classes_held=0` → **NaN** (undefined), not 0; `learn_tsem_volume_total` with rows that
  sum to 0 → 0 (that is a real zero-volume semester).
- `NULL` is returned when the source record is unavailable: no `attendance_weekly`/`student_learning_activity`
  rows at T, or NULL source columns (`pre_endsem_assessment_pct`, etc.).
- Derivation fills **only when the stored value is missing** (never overwrites a real 6A value).

## 8. Changes made

| File | Change |
|---|---|
| `ml/v2/m3_at_risk_prediction/inference/predictor.py` | Added `_recover_prior_history()` (training-exact Tier‑1B recovery, point-in-time, missing-stays-missing) and wired it into `predict_for_student()` to fill only missing Tier‑1B values. Model, features, ordering, preprocessing, threshold untouched. |
| `ml/v2/m3_at_risk_prediction/tests/test_m3_v2.py` | Added `TestRecoverPriorHistory` (6 tests) and `TestMissingVsZeroAggregates` (5 tests). |
| `lib/m3v2-prediction.ts` | Added `M3V2_FEATURE_LABELS`, `m3V2FeatureLabel()`, `m3V2SignalValue()` (human units; missing → "Not available"). |
| `components/student/ml-insights/m3v2-card.tsx` | Signals header → "Key signals used by the model"; human labels + typed values; missing shown as "Not available" with honest note. |
| `lib/m3v2-prediction.test.ts` | New frontend tests for labels, units, missing-vs-zero, risk tones. |

## 9. Tests & verification

- ML M3 module suite: **53 passed** (`ml: .venv/Scripts/python -m pytest v2/m3_at_risk_prediction/tests/`).
- Backend M3: `tests/test_m3v2_prediction.py` + `tests/test_m2_m3_progression.py` → **40 passed** (6A end-to-end via the real Supabase pool unchanged).
- Frontend: **200 passed** (incl. new m3v2 helper tests), `npx tsc --noEmit` clean, `npm run lint` (no new issues; 2 pre-existing errors in `lib/i18n/i18n.test.ts`/`student-api.test.ts`), `npm run build` OK.

## 10. Real-student before/after verification

STU000001 (observation semester 7 → semester 8), **same artifact (m3_v2_at_risk v2.0)**:

| | Before | After |
|---|---|---|
| `probability_at_risk` | 0.0868 | **0.0868** (unchanged) |
| risk flag (≥ 0.640) | false | false |
| `attendance_aggregate_pct` | `—` | **87.35** |
| `sgpa_drift` / previous_backlog / backlog_change / cumulative | NaN (median-imputed) | 0 / 0 / 0 / 0 (derived, training-exact) |
| `learn_tsem_volume_total`, `att_tsem_total_pct`, `subj_pre_endsem_pct_mean`, … | `—` | `Not available` (no source data) |

Why the probability is unchanged for this student: the recovered features carry values very near the
training medians (backlog analytics ≈ 0; attendance_aggregate ≈ semester_attendance_percentage, already
near-median) and the RF estimate is not threshold-sensitive here. **All 80 real students** (batch run
through the production predictor): probabilities 0.000–0.258 (median 0.1005, mean 0.1016), **0 of 80
flagged at-risk**; `attendance_aggregate_pct` now resolves for all 80. Six of the top-10 signals per
student remain legitimately "Not available" (weekly/assignment features) until those tables are loaded
for the real cohort.

## 11. UI output & signal semantics

- Signals header is now **"Key signals used by the model"** — signals are the top **feature values**
  the model weighted (RF `feature_importances_`), never causal claims.
- Raw internal feature names are never shown; human labels + units (%, SGPA to 2dp, counts as integers).
- Missing values render "Not available" (italic, muted) with an explanatory note; `probability_at_risk`
  keeps "Estimated risk" framing (never "will fail").

## 12. Constraints honored

- No retraining; `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` untouched.
- No target/threshold change (0.640), no feature added/removed (still exactly 35), ordering preserved.
- Supabase remains **read-only** for inference: the fix is in the production feature assembly, matching
  the training-computed columns without writing to the DB.
- M1 V3 and M2‑TP untouched.

## 13. Known limits (honest non-fixes)

- `att_tsem_total_pct` / `learn_tsem_volume_total` (and siblings) stay genuinely missing until
  `attendance_weekly` / `student_learning_activity` rows are loaded for STU0000xx — a **data-load gap**
  (`backend/etl`), not an inference bug. The persistence path (e.g. `admin_ml_generation_service`) is the
  right place to backfill those tables for the real cohort.
- `assignment_score` / `quiz_avg_marks` / `submission_delay_days` / `pre_endsem_assessment_pct` subject
  columns are NULL for the real cohort; subject aggregates for those features therefore stay NaN
  (median-imputed at inference). If these should exist for real students, populate at the ETL layer.
- Recovered values carry the source precision of `semester_*` columns (±0.005 vs. 3dp training storage).