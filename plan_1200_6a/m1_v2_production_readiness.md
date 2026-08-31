# M1 v2 — Production Readiness Report

**Model:** `m1_v2_subject_endmarks` v2.0
**Target:** `end_sem_marks` (clip [0.0, 70.0])
**Cohort:** CSE 6A — 1,200 students / 68,400 labeled rows
**Trained:** 2026-08-31 (deterministic; verified reproducible)
**Status:** ✅ **READY for ML-side integration review** (backend API wiring intentionally deferred per project phase)

---

## 1. Executive Summary

M1 V2 is a clean rebuild of the legacy M1 predictor on **real, non-synthetic** data for the
1,200-student CSE 6A cohort. It is internally consistent, leakage-free by construction and by
runtime verification, and it beats both naive baselines on a genuinely held-out semester.

| Signal | Value |
|---|---|
| CV MAE (GroupKFold, student-grouped) | **6.319 ± 0.040** |
| CV R² | **0.434** |
| Temporal MAE (sem 7) | **6.302** |
| Temporal R² | **0.423** |
| Mean-baseline MAE (sem 7) | 8.413 |
| Prior-semester-mean MAE (sem 7) | 7.509 |
| Lift over mean baseline | **~2.11 MAE (25%)** |
| Lift over prior-sem mean baseline | **~1.21 MAE (16%)** |
| Leakage check | **PASS** (no forbidden features) |
| Reload + prediction test | **PASS** |
| Test suite | **51/51 pass** |

Legacy M1 V1 reported CV MAE 3.18 / R² 0.82, but per the prior audit those numbers are
**NOT trustworthy** (synthetic, near-stationary 80-student data). V2's higher MAE is the honest
real-data result, not a regression. See `m1_v2_validation_report.md` §3.

---

## 2. Readiness Checklist

| Area | Status | Evidence |
|---|---|---|
| Data integrity (FK, grain, row counts) | ✅ PASS | loader + `check_joins`; 68,400 rows, 0 duplicate grains |
| Feature contract (39 features, no forbidden) | ✅ PASS | `m1_v2_feature_contract.md`; leakage check in training |
| Leakage-free (point-in-time + forbidden list) | ✅ PASS | runtime check + `TestLeakageByConstruction` |
| GroupKFold by student (no student leakage) | ✅ PASS | `cv.py`; `TestGroupKFoldInputs` |
| Temporal hold-forward (train 1–6, val 7) | ✅ PASS | sem 7 held out entirely from training |
| Baselines measured on same holdout | ✅ PASS | mean + prior-semester-mean; model beats both |
| Model selection by evidence (not flagging) | ✅ PASS | ridge lowest mean MAE; verified broadly |
| No overfitting (train-val gap) | ✅ PASS | gap ≈ 0 to slightly negative across models |
| Artifact reload + prediction | ✅ PASS | Phase 11 tests; `TestArtifactInvariants` |
| Reproducibility | ✅ PASS | two independent runs → identical metrics |
| Test suite | ✅ PASS | 51/51 (config, features, leakage, CV, artifact, predictor) |
| Supabase read-only compliance | ✅ PASS | NO ALTER/CREATE/DROP/INSERT/UPDATE/DELETE issued |

---

## 3. Model Selection Rationale

All four candidates were evaluated on the same GroupKFold(5) × 3-seed scheme and the same
semester-7 temporal holdout:

| Algorithm | CV MAE | CV R² | Temporal MAE | Temporal R² |
|---|---|---|---|---|
| **ridge** | **6.319** | 0.434 | **6.302** | 0.423 |
| hist_gbm | 6.349 | 0.430 | 6.343 | 0.420 |
| xgboost | 6.334 | 0.433 | 6.334 | 0.422 |
| random_forest | 6.612 | 0.390 | 6.611 | 0.378 |

- **ridge** selected: lowest mean CV MAE, simplest model, tied for best temporal MAE.
- All four are within ~0.3 MAE of each other → the result is **stable across model families**,
  increasing confidence it reflects real signal rather than a single algorithm's quirk.
- Ridge + StandardScaler is the lightest production dependency (sklearn-only).

---

## 4. Honest Assessment of the R² = 0.43 Figure

R² 0.43 is **modest but legitimate** for real exam-score prediction. Caveats the reader must
carry:

1. Legacy V1's heuristic threshold `BASELINE_INSUFFICIENT_R2 = 0.70` was inherited from
   synthetic-data expectations and is **not applicable** to real data. It should not gate
   this model.
2. The `config.BASELINE_INSUFFICIENT_MAE = 5.0` / `R2 = 0.70` knobs are intended for a
   future **ablation / feature-selection phase (Stage B)** which is OUT of scope for this
   training+validation phase. They do not imply the current model is failing.
3. The strongest evidence of skill is **lift over the prior-semester-mean baseline**
   (6.302 vs 7.509) on a semester never seen in training. A model that merely memorized the
   target family would match, not beat, the prior-mean baseline.

**Recommendation:** Do NOT judge M1 V2 against V1's inflated R². Judge it against baselines
and against the honest CV/temporal spread — both of which it passes.

---

## 5. Leakage & Data-Safety Verification

- `select_features` drops every forbidden column; leakage verified **after** encoding.
- `TestLeakageByConstruction` injects forbidden columns and asserts they never reach `X`.
- GroupKFold groups by `student_id` → no student appears in both train & val in CV.
- Temporal holdout excludes all semester-7 rows from training.
- Preprocessing (`M1Preprocessor` imputer, `StandardScaler`) is fit **on training folds only**.
- `Semester 8` rows are excluded from all fit (only used at inference time if deployed during sem 8);
  no future-semester data is used for training.
- No `skill_profile` / `career_preferences_v2` / `placement` features (future/post-graduation leakage).

---

## 6. Artifact & Inference Readiness

- **Artifact:** `ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib`
- Contains: `model` (ridge), `preprocessor` (median imputer), `scaler` (StandardScaler),
  `feature_names` (39, == preprocessor.feature_names), `metadata`.
- Reload + prediction test PASS; predictions clipped to [0, 70].
- Inference entry point: `M1V2Predictor` — thread-safe singleton, loads once, read-only.
  Two APIs:
  - `predict_from_features(X)` — synchronous, for batch/offline use.
  - `predict_for_student(student_id, conn)` — async, DB-backed, for backend integration.
- Grade-band derivation (`_grade_from_marks`) returns band + label.

**Not yet done (deferred by project phase):**
- Backend/FastAPI wiring to serve predictions via HTTP **— intentionally STOPPED per the
  current training+validation phase.**
- Load/concurrency smoke tests against the live inference path with the DB.
- Model monitoring / drift detection.

---

## 7. Known Limitations (must be carried into production)

1. **Single-cohort generalization:** all 1,200 students are CSE 6A. Cross-department
   generalization is unproven until a second cohort is available.
2. **Temporal holdout is same-cohort, later-semester:** sem 7 students also appear in
   sems 1–6. A truly unseen *cohort* holdout is not possible with current data and is the
   single most important future validation.
3. **Self-reported features:** `mental_stress_level`, `study_hours_per_week` carry
   self-reporting bias.
4. **No uncertainty/interval:** predictions are point estimates. Add conformal prediction or
   quantile regression before deploying to high-stakes uses.
5. **Range coverage:** training labels span end_sem_marks ≈ 2–70; extreme values are poorly
   calibrated.

---

## 8. Recommendation

- **M1 V2 model: deployable as the validated M1 predictor** once the backend integration
  phase begins (currently deferred).
- **Do not** modify or delete legacy `ml/src/m1/` until the replacement rollout is decided.
- **Do not** quote V1 metrics (MAE 3.18 / R² 0.82) in any user-facing or monitoring context;
  they are synthetic-data artifacts.
- **Next priority when phase allows:** acquire a second, non-6A cohort for a true
  unseen-cohort temporal validation, and add prediction intervals.

---

*Generated as part of the M1 V2 (Subject Performance / Marks Prediction) deliverable set:
`m1_v2_data_audit.md`, `m1_v2_feature_contract.md`, `m1_v2_validation_report.md`, and this
`m1_v2_production_readiness.md`.*
