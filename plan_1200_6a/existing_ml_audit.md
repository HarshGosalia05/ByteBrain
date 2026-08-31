# Existing ML Stack — Read-Only Audit (M1, M2, M3, M4)

**Date:** 2026-08-31
**Scope:** Full read-only inventory & classification of the existing ML stack.
**Mandate enforced:** No files modified, deleted, retrained, or re-served. No Supabase / frontend / GenAI changes. Nothing written except this audit + the ML v2 architecture proposal under `plan_1200_6a/`.

---

## 0. Executive Summary

The existing ML stack is a **V1 / single-cohort, academically-synthetic prototype**. M1, M2, M3 are classical ML (sklearn) models trained and evaluated on **synthetic, deterministic seed data** (80 students, 500 semester rows). M4 is a rule-based scoring engine (not ML).

The stack is **internally disciplined** — the code contains strong leakage guards (GroupKFold by student, forbidden-feature blocklists, deployment-row exclusion, honest resubstitution labeling, a validation gate). **That discipline is real and should be reused.** However, the **reported metrics are NOT trustworthy as evidence of real-world predictive skill** for any of M1/M2/M3, for two compounding reasons:

1. **The data is synthetic and near-stationary per student.** Consequences-grade features (`semester_percentage`, `semester_sgpa`, `internal_marks`, `mid_sem_marks`, `attendance`) correlate 0.86–0.99 with their own next-period / final targets. High R² / low MAE is a property of the deterministic generator, not model skill.
2. **Statistical sample is almost nonexistent.** M3's positive class is 6 students / 28 rows. M1 and M2 each rely on ~80 students. Model selection and "gains" between similar algorithms are not statistically significant.

**Headline conclusion per model:**

| Model | Current status | Reported metrics | Are metrics trustworthy? |
|---|---|---|---|
| M1 | READY per pipeline; temporal multi-holdout passed | MAE 3.18 / R² 0.82 (CV); MAE ~3.23 (temporal) | **No** — synthetic near-stationary data; gap vs real world unknown |
| M2 | READY per pipeline; cohort expanded CSE+BBA | MAE 1.10 / R² 0.997 (percentage); MAE 0.15 / R² 0.991 (sgpa) | **No** — R² 0.99 is an autocorrelation artifact, not skill |
| M3 | **BLOCKED** (validation gate FAIL) | F1 0.80 / ROC-AUC 1.00 | **No** — 6 positive students; small-sample artifact |
| M4 | RULE-BASED engine (shipped) | Deterministic score 13.15–94.41 | N/A (no model); weights are hand-set policy |

**Recommended posture:** Build a clean, isolated **ML v2** architecture whose first job is to acquire a **real, non-synthetic, multi-cohort labeled dataset** and to re-derive every metric on genuinely held-out future cohorts. Do not trust any V1 headline number.

---

## 1. Inventory of Every ML Component

### 1.1 M1 — Subject End-Marks Prediction (regression)

| Item | Path |
|---|---|
| Model/config | `ml/src/m1/config.py` |
| Data + feature engineering | `ml/src/m1/data.py`, `ml/src/features.py`, `ml/src/feature_config.py`, `ml/src/feature_data.py` |
| Training | `ml/src/m1/train_m1.py` |
| Evaluation | `ml/src/m1/evaluate.py` |
| Temporal validation | `ml/src/m1/temporal.py`, `ml/src/m1/multi_holdout.py`, `ml/src/m1/readiness.py` |
| Artifact | `ml/artifacts/models/m1_subject_endmarks.joblib` (441 KB, 2026-08-12) |
| Report | `ml/reports/m1_report.md`, `ml/reports/m1_verification.md` |
| Tests | `ml/tests/test_m1.py`, `test_m1_temporal.py`, `test_m1_multi_holdout.py`, `test_m1_readiness.py`, `test_features.py` |
| Verify scripts | `ml/verify_m1.py`, `ml/verify_m1_temporal.py`, `ml/verify_m1_multi_holdout.py`, `ml/verify_m1_readiness.py`, `ml/verify_feature_engineering.py` |

**Details**
- **Implementation path:** `ml/src/m1/` (train_m1.py orchestrator).
- **Artifact path:** `ml/artifacts/models/m1_subject_endmarks.joblib`.
- **Model:** `HistGradientBoostingRegressor` (selected over ridge / xgboost; 5-fold CV), stored as a dict `{model, preprocess, feature_names, feature_tier, metadata}`.
- **Target:** `end_sem_marks` (0–70, clipped). Prediction point = during semester T after internal/mid/attendance recorded, before end-exam.
- **Features (12 encoded):** `internal_marks, mid_sem_marks, attendance_percentage, credits, semester_no, subject_type_* (4), department_name_* (2), is_male`. Forbidden list (15) enforced.
- **Training dataset/cohort:** CSE+BBA 80 students, 3850 performance rows → 3293 labeled / 557 deploy (hardcoded assert).
- **Validation methodology:** GroupKFold(5) by student_id; 3 seeds for model selection; optional ablation (Stage B, OFF); **temporal multi-holdout** (forward windows with strict past→future order).
- **Validation metrics:** CV MAE 3.18±0.11 / RMSE 3.84 / R² 0.82; temporal held-out mean MAE ~3.23.
- **Leakage status:** Class-documented abundant guards; **no explicit target leakage appears**. Caveats: `build_dataset` does not drop forbidden cols itself (defense-in-depth only); `prior_avg_end_marks` mixes the target family (ablation-only, off); student identity is deliberately NOT masked across temporal windows (reported).
- **Metrics trustworthiness:** **LOW/UNVERIFIED.** Data is synthetic & near-stationary; internal (r=0.81), mid-sem (r=0.86), and attendance (r=0.87) are highly predictive *within the same semester*, so the model is essentially interpolating a deterministic generator.
- **Production usage:** Readiness says "technically READY for offline inference, NOT approved for production/API/dashboard/student-facing". External FastAPI serves `/predict/insights`.
- **Dependencies:** scikit-learn 1.9.0, joblib, pandas, numpy (pinned); shares `features.py`, `feature_config.py`, `registry.py`, `inference.py`.
- **Recommendation:** **REBUILD** (on real data); keep the leakage-guard + temporal-validation code patterns.

### 1.2 M2 — Next-Semester Performance (regression, multi-target)

| Item | Path |
|---|---|
| Config | `ml/src/m2/config.py` |
| Data + targets | `ml/src/m2/data.py` |
| Training | `ml/src/m2/train_m2.py` |
| Evaluation | `ml/src/m2/evaluate.py` |
| V1 integration | `ml/src/features/v1_m2_regression.py` |
| Artifact | `ml/artifacts/models/m2_next_semester_performance.joblib` (570 KB, 2026-08-28) |
| Report | `ml/reports/m2_report.md` |
| Verify | `ml/verify_v1_m2_regression.py`, `ml/run_m2_m3_cohort_expansion.py` |
| Tests | `ml/tests/test_v1_m2_regression.py`, `test_v1_training_dataset.py` |

**Details**
- **Implementation path:** `ml/src/m2/` (train_m2.py) + V1 path (`v1_m2_regression.py`).
- **Artifact path:** `ml/artifacts/models/m2_next_semester_performance.joblib` — a dict of two sklearn Pipelines (`{next_semester_percentage, next_semester_sgpa}`).
- **Model:** per-target `HistGradientBoostingRegressor` (chosen by lowest mean MAE among ridge/hist_gbm/xgboost).
- **Targets:** `next_semester_percentage`, `next_semester_sgpa` (built via `shift(-1)` per student — future outcome).
- **Features (11 raw → 12 encoded):** `semester_no, subjects_registered, credits_registered, credits_earned, semester_total_marks, semester_percentage, semester_sgpa, semester_attendance_percentage, backlog_count, department_name (2), is_male`.
- **Training dataset/cohort:** CSE+BBA 80 students → 300 labeled (V1 CSE-only report) or 420 labeled (multi-dept); last semester per student is deployment.
- **Validation methodology:** GroupKFold(5) by student_id; V1 adds student-isolation & deployment-exclusion checks.
- **Leakage status:** Shifted-future target is constructively correct; no target leakage. **BUT** see the autocorrelation finding in §1.2.1.
- **Validation metrics:** percentage MAE 1.102 / R² **0.9972**; sgpa MAE 0.152 / R² **0.9911**.
- **Metrics trustworthiness:** **NOT TRUSTWORTHY.** See §1.2.1 — near-perfect R² is an artifact of synthetic, near-stationary per-student data, not genuine skill. Any production claim of "99.7% explained variance" is invalid.
- **Production usage:** READY per pipeline; served via `/predict/insights`. **Suspected overclaimed.**
- **Dependencies:** sklearn 1.9.0, joblib, pandas, xgboost; shares `features.py` contract.
- **Recommendation:** **REBUILD** (real data, sanity-check R²; treat near-1.0 R² as a red flag, not a win).

#### 1.2.1 — M2 autocorrelation/leakage finding (empirical verification)
Independently computed on raw data (training rows = 420):

| Current feature (T) | corr with next % (T+1) | corr with next sGPA (T+1) |
|---|---|---|
| `semester_percentage` | **0.9919** | 0.9619 |
| `semester_sgpa` | 0.9632 | **0.9749** |
| `semester_total_marks` | 0.9121 | 0.8872 |
| `semester_attendance_percentage` | 0.9804 | 0.9617 |

Mean per-student absolute change in percentage between consecutive semesters ≈ **1.31 points**; in SGPA ≈ **0.20**. The generator produces near-constant per-student trajectories, so the model can "predict the future" almost perfectly from the present. **This is why R²≈0.99.** Not target leakage, but not real predictive signal either — the metric is structurally inflated and must not be read as production-readiness.

### 1.3 M3 — Next-Semester At-Risk (binary classification)

| Item | Path |
|---|---|
| Retrain + feedback | `ml/src/retrain_m3.py` |
| Baseline / experiment / gate | `ml/src/features/v1_baseline_m3.py`, `v1_m3_experiment.py`, `v1_m3_validation_gate.py`, `v1_m3_cohort_expansion.py` |
| Labels | `ml/src/features/v1_label_builder.py` |
| Dataset / split / validation | `ml/src/features/v1_dataset.py`, `v1_split.py`, `v1_split_config.py`, `v1_split_validation.py`, `v1_split_coverage.py`, `v1_config.py`, `v1_validation.py` |
| Cohort gates | `ml/src/features/v1_cohort_dataset.py`, `v1_later_cohort_gate.py` |
| Feedback audit | `ml/src/features/v1_feedback_audit.py`, `ml/src/feedback_labels.py` |
| Artifact | `ml/artifacts/models/m3_next_semester_at_risk.joblib` (2 KB, 2026-08-14) |
| Report | `ml/reports/m3_report.md` |
| Verify / tests | `verify_v1_m3_*.py`, `test_v1_m3_*.py`, `test_retrain_m3.py`, `test_feedback_labels.py` |

**Details**
- **Implementation path:** `ml/src/features/*m3*` (baseline/experiment) + `ml/src/retrain_m3.py` (feedback-informed).
- **Artifact path:** `ml/artifacts/models/m3_next_semester_at_risk.joblib` — a single sklearn Pipeline (`SimpleImputer(median) → StandardScaler → LogisticRegression(class_weight='balanced', max_iter=1000)`).
- **Target:** `is_at_risk_next_sem` = next-result FAIL/ATKT **or** next backlog_count>0.
- **Features (11→12 encoded):** identical contract to M2 (CSE+BBA).
- **Training dataset/cohort:** CSE+BBA → 420 labeled rows: **392 negative / 28 positive**, from **only 6 unique positive students** (STU000032, 041, 052, 060, 064, 075).
- **Validation methodology:** GroupKFold(5) by student_id for baseline/experiment/improvement; **StratifiedKFold(5)** in `retrain_m3.py` (methodology divergence — see §1.3.1).
- **Validation metrics (reported):** Accuracy 1.000, Precision 0.800, Recall 0.800, F1 0.800, ROC-AUC 1.000.
- **Metrics trustworthiness:** **NOT TRUSTWORTHY / invalid.** The Validation Gate itself returns **FAIL** and inference is **BLOCKED** (`v1_inference_contract.py`: `M3_READINESS = BLOCKED`). Perfect/deterministic metrics on 2-student informative folds are small-sample artifacts. **M3 is correctly NOT served in production.**
- **Leakage status:** Guarded (GroupKFold in the main path), but **`retrain_m3.py` uses StratifiedKFold** (no student grouping) — a latent leakage/methodology divergence. `retrain_m3.py` also uses a **non-canonical label** (`next_sgpa < 4.0` OR backlog>0) and a **schema alias** (`department_code AS department_name`) that is inconsistent with the canonical `v1_label_builder` rule.
- **Production usage:** **BLOCKED** — correct. No production prediction.
- **Dependencies:** sklearn 1.9.0, joblib, pandas, asyncpg (via prediction_service).
- **Recommendation:** **REBUILD** — but only after sufficient real positive-class data exists. The existing gate logic is exactly right and must be carried into v2.

#### 1.3.1 — M3 issues to carry forward / avoid
1. **StratifiedKFold vs GroupKFold divergence** in `retrain_m3.py` — must not recur in v2.
2. **Non-canonical label rule** (`sgpa<4.0`) in `fetch_historical_training_dataset` — must be unified with the canonical label builder.
3. **Schema alias mismatch** (`department_code` vs `department_name`) in retraining SQL.
4. **Correctly blocklisted** — `v1_inference_contract.predict_m3` returns BLOCKED with no production prediction. Good.

### 1.4 M4 — Career Readiness (rule-based scoring)

| Item | Path |
|---|---|
| Rule engine (class) | `ml/src/m4/engine.py` |
| Build/serialize | `ml/src/m4/build_m4.py` |
| Standalone engine | `ml/m4_career_readiness.py` |
| **Legacy supervised-ML (abandoned)** | `ml/src/m4/config.py`, `data.py`, `train_m4.py`, `evaluate.py` |
| **Backup of legacy** | `ml/src/m4_backup/` (config.py, data.py, evaluate.py) |
| Artifact (rule engine) | serialized via `build_m4.py` (engine object) — see note |
| Output | `ml/data/final/m4_career_readiness_scores.csv`, `ml/m4_career_readiness_scores.csv` |
| Report | `ml/reports/m4_report.md` (note: a stale `.md.bak` also exists) |
| Tests | `ml/tests/test_*m4*` (via inference/explain) |

**Details**
- **Implementation path (shipped):** `ml/m4_career_readiness.py` (682-line standalone) and mirrored `ml/src/m4/engine.py`.
- **Artifact path:** `registry` treats M4 as `RULE_BASED` (no ML artifact). **Note:** `ml/src/m4/build_m4.py` does serialize the engine to a `.joblib`; the report's claim that "no .joblib is created" is inconsistent with `build_m4.py`. Low severity (it's a config object, not a trained model).
- **Model:** **Not ML.** Deterministic 100-point scoring engine: academic_performance 35 + growth_trend 10 + career_preparedness 25 + lifestyle_discipline 30; levels High≥75 / Medium≥50 / else Low. Weights are **hand-set policy**, not tuned.
- **Target:** `career_readiness_score` / `career_readiness_level`.
- **Features:** students / semester summary / career_preferences / lifestyle_survey (avg percentage & attendance, total backlogs, pass ratio, percent slope, internship, certification, forward planning, study hours, sleep, wellbeing, stress, physical activity).
- **Training dataset/cohort:** not trained; scored on all 80 students (500 semester rows, 80 career, 80 lifestyle).
- **Validation methodology:** deterministic checks (score range, level set, no poisoned columns, repeatability). Not statistical.
- **Leakage status:** No trained model → no train/test leak. Minor: academic aggregates include the in-progress semester in "prior" means; rows with NaN on 3 key fields are silently dropped. **`placement_readiness_level` is explicitly poisoned/dropped** — good (it was the synthetic leak that triggered the rewrite).
- **Metrics:** Score 13.15–94.41, mean 64.34, median 70.82; High=19, Medium=46, Low=15.
- **Production usage:** Served (scoring + optionally GenAI career guidance).
- **Recommendation:** **KEEP** the rule engine as a transparent baseline, but move it into the v2 registry with declared weight provenance; **ARCHIVE** the legacy supervised-ML version (`ml/src/m4/{train,data,config,evaluate}.py` + `ml/src/m4_backup/`).

---

## 2. Shared Infrastructure Inventory

| Component | Path | Role | Classification |
|---|---|---|---|
| ML package | `ml/__init__.py` | package marker | A (tiny) |
| Registry / safe loader | `ml/src/registry.py` | model discovery + typed load + cache | **A** (reuse in v2) |
| Central inference | `ml/src/inference.py` | per-model predict wrappers | **A** (reuse) |
| Prediction service | `ml/src/prediction_service.py` | async DB-backed per-student predict + cache | **B** (cache TTL; sync-in-async) |
| Persistence contract | `ml/src/prediction_persistence.py` | json-safe row mapping | **A** |
| Explainability | `ml/src/explain.py` | grounded rule-based explanations | **A** |
| Feedback labels | `ml/src/feedback_labels.py` | feedback→label mapping | **B** (heuristic "latest wins") |
| Feature contracts | `ml/src/features.py`, `feature_config.py` | per-model raw/encoded feature contracts | **A** (hardcoded 2-dept — brittle) |
| DB feature data | `ml/src/feature_data.py` | read-only SQL builders | **B** (CSE/BBA hardcoded) |
| V1 validation suite | `ml/src/features/v1_*` | 13+ check validators, gates, audits | **A** (carry the *methodology*) |
| Requirements | `ml/requirements.txt` | sklearn 1.9.0, pandas, numpy, joblib | **B** (missing asyncpg dep) |
| Reports | `ml/reports/*.md` (11 files) | audit/verification reports | E (see §3) |

---

## 3. Classification Ledger (A–E)

Reference: the full-inventory ledger below. `:path` suffixes are illustrative parents.

| Component | Class | Notes |
|---|---|---|
| `m1` config/data/train/eval/temporal/multi_holdout/readiness | **A→B** | Methodology reusable (A); trained model + metrics obsolete (B) |
| `m1` histogram-gbm artifact | **C** | Synthetic-data artifact; rebuild |
| `m2` config/data/train/eval + V1 regression | **A→B** | Pipeline reusable; artifact metrics invalid |
| `m2` artifact | **C** | Near-perfect R² artifact; rebuild |
| `m3` baseline/experiment/gate/label_builder/dataset/split | **A** | Carry the gate + label discipline into v2 |
| `m3` artifact | **C** | BLOCKED; no production use; archive |
| `m3` `retrain_m3.py` (feedback retraining) | **D→B** | StratifiedKFold (no group) = leakage divergence; non-canonical label; schema alias → **blocked from reuse until fixed** |
| `m3` feedback_labels latest-wins | **B** | Heuristic; validate against ground truth |
| `m4` rule engine (`engine.py`, `m4_career_readiness.py`) | **A** | Transparent baseline; keep |
| `m4` build_m4.py | **B** | Writes artifact contrary to report; weak reload check |
| `m4` legacy supervised-ML (`src/m4/{config,data,train,evaluate}.py`) | **C** | Abandoned; synthetic target; archive |
| `m4_backup/` | **C** | Duplicate of legacy; archive/merge |
| `m4_report.md.bak` | **E** | stale backup; archive |
| `registry.py` | **A** | Reuse core loader in v2 |
| `inference.py`, `prediction_persistence.py`, `explain.py` | **A** | Reuse |
| `prediction_service.py` | **B** | Cache without TTL; blocking sync predict; deprecate `_fetch_student_subjects` |
| `features.py` / `feature_config.py` | **B** | Encoded-column contracts hardcode 2 depts — make data-driven in v2 |
| `feature_data.py` | **B** | SQL hardcoded to CSE/BBA; generalize |
| `requirements.txt` | **B** | Missing `asyncpg`; pin versions |
| V1 validation/gates/audits | **A** | Move into v2 as first-class reusable validators |
| `verify_*.py` throwaway scripts (18) | **B** | Replace with proper test/pytest coverage in v2 |
| Reports (`m1/m2/m3/m4_*.md`, ML-08→11) | **E** | Descriptive; do NOT cite metric numbers as evidence |

---

## 4. Per-Model Report (mandated fields)

### M1 — Subject End-Marks
- **Implementation path:** `ml/src/m1/` (train_m1.py) + `ml/src/features.py` / `feature_data.py`
- **Artifact path:** `ml/artifacts/models/m1_subject_endmarks.joblib`
- **Training dataset/cohort:** 80 students (CSE+BBA), 3293 labeled / 557 deploy performance rows
- **Target:** `end_sem_marks` [0,70]
- **Features:** 12 encoded (internal/mid/attendance/credits/semester_no/subject_type/department/gender)
- **Leakage status:** No explicit target leakage; same-semester predictive signals are temporally valid but data is synthetic
- **Validation methodology:** GroupKFold(5) student-isolated; 3-seed selection; temporal multi-holdout forward windows
- **Validation metrics:** CV MAE 3.18 / R² 0.82; temporal MAE ~3.23
- **Metrics trustworthy?** **No.** Synthetic near-stationary data inflates apparent skill; real-world generalization unknown.
- **Production usage status:** offline inference "READY" but **not** approved for production/API/dashboard
- **Dependencies:** sklearn 1.9.0, joblib, pandas, xgboost; shares features/registry/inference
- **Recommendation:** **REBUILD** (on real, multi-cohort data) — reuse temporal-validation + guard code

### M2 — Next-Semester Performance
- **Implementation path:** `ml/src/m2/` + `ml/src/features/v1_m2_regression.py`
- **Artifact path:** `ml/artifacts/models/m2_next_semester_performance.joblib`
- **Training dataset/cohort:** CSE+BBA 80 students → 420 labeled; last-semester rows = deployment
- **Target:** `next_semester_percentage`, `next_semester_sgpa`
- **Features:** 11→12 encoded, same M2/M3 contract
- **Leakage status:** No target leakage; **R²≈0.99 is autocorrelation artifact** (empirically verified, §1.2.1)
- **Validation methodology:** GroupKFold(5) student-isolated + V1 checks
- **Validation metrics:** % MAE 1.102 / R² 0.9972; sGPA MAE 0.152 / R² 0.9911
- **Metrics trustworthy?** **No.** Structurally inflated; near-perfect R² on synthetic stationary data.
- **Production usage status:** reported READY & served — **overclaimed**
- **Dependencies:** sklearn 1.9.0, xgboost, joblib, pandas
- **Recommendation:** **REBUILD** (real data; treat near-1.0 R² as a red flag; add genuine holdout cohort)

### M3 — At-Risk
- **Implementation path:** `ml/src/features/v1_*m3*` + `ml/src/retrain_m3.py`
- **Artifact path:** `ml/artifacts/models/m3_next_semester_at_risk.joblib`
- **Training dataset/cohort:** CSE+BBA → 420 rows, 6 positive students (28 positive rows)
- **Target:** `is_at_risk_next_sem`
- **Features:** 11→12 encoded (M2/M3 contract)
- **Leakage status:** main path guarded; `retrain_m3.py` diverges (StratifiedKFold + non-canonical label + schema alias)
- **Validation methodology:** GroupKFold(5) baseline/experiment; validation gate; split coverage; later-cohort gate
- **Validation metrics:** reported F1 0.80 / ROC-AUC 1.00 (from `m3_report.md`)
- **Metrics trustworthy?** **No / invalid.** 6 positive students; gate = FAIL; inference = BLOCKED.
- **Production usage status:** **BLOCKED** — not served (correct)
- **Dependencies:** sklearn 1.9.0, joblib
- **Recommendation:** **REBUILD** once sufficient real positive class exists; keep gate as hard requirement. Do NOT lift metrics.

### M4 — Career Readiness
- **Implementation path (shipped):** `ml/m4_career_readiness.py`; mirrored `ml/src/m4/engine.py`
- **Artifact path:** none (rule-based); engine object serialized by `build_m4.py`
- **Training dataset/cohort:** not trained; scored 80 students
- **Target:** `career_readiness_score` / `level`
- **Features:** academic + trend + career + lifestyle (declared)
- **Leakage status:** no trained model; `placement_readiness_level` poisoned/dropped (good)
- **Validation methodology:** deterministic checks only
- **Validation metrics:** score 13.15–94.41; High 19 / Medium 46 / Low 15
- **Metrics trustworthy?** N/A (not ML); weights are policy, not evidence.
- **Production usage status:** served (score + optional GenAI guidance)
- **Dependencies:** pandas, numpy
- **Recommendation:** **KEEP** (transparent baseline); **ARCHIVE** legacy supervised-ML + `m4_backup`.

---

## 5. Migration Table (requested)

| Model | Existing implementation | Status | Keep? | Rebuild? | Reason |
|---|---|---|---|---|---|
| **M1** | `ml/src/m1/` (train/eval/temporal) + `ml/artifacts/models/m1_subject_endmarks.joblib` | READY (offline); not prod-approved | Keep **methodology** (`temporal.py`, `multi_holdout.py`, leak guards); archive trained artifact | **Yes** | Synthetic near-stationary data; metrics not evidence of real skill; rebuild on real cohorts |
| **M2** | `ml/src/m2/` + `v1_m2_regression.py` + artifact | READY; served | Keep **pipeline code**; archive artifact | **Yes** | R²≈0.99 is autocorrelation artifact (verified), not genuine skill; overclaimed production readiness |
| **M3** | `ml/src/features/v1_*m3*` + `retrain_m3.py` + artifact | **BLOCKED** (gate FAIL; not served) | Keep **validation gate + label builder + GroupKFold**; archive artifact; **block `retrain_m3.py` reuse** until leakage/label divergences fixed | **Yes** | 6 positive students → statistically invalid metrics; retraining path has leakage divergence |
| **M4** | `ml/m4_career_readiness.py`, `ml/src/m4/engine.py`; legacy supervised-ML at `ml/src/m4/{train,data,config,evaluate}.py` + `m4_backup/` | RULE-BASED (served) | **Keep** rule engine + `engine.py`; **ARCHIVE** legacy supervised-ML + old `.bak`/backup dir | **No** (rule engine) | M4 is intentionally rule-based, not ML; legacy ML version learned a synthetic target and is obsolete/duplicated |

---

## 6. Consolidated Findings & Risks

### What is genuinely worth keeping (A)
- GroupKFold-by-student validation discipline (all models).
- Deployment-row exclusion & forbidden-feature blocklists (all models).
- M3's **statistical validation gate** that correctly refuses to bless underpowered models. This is the single most valuable piece of the stack.
- M3's **canonical label builder** (`v1_label_builder.py`) with conflict/ambiguity detection.
- Temporal multi-holdout machinery (M1).
- The **registry / inference / persistence / explainability** service layer (clean, typed, json-safe).

### What is obsolete/duplicate (C)
- All three trained artifacts: produced on synthetic data; their headline numbers must not be quoted.
- `ml/src/m4_backup/` (byte-identical duplicate of legacy m4).
- Legacy supervised-ML M4 (`train_m4.py`, `evaluate.py`, `data.py`, `config.py`).
- `m4_report.md.bak`, `verify_*.py` throwaway scripts (superseded by tests).

### What is unsafe / must be blocked or fixed (D)
- **`retrain_m3.py`**: StratifiedKFold (no student grouping = latent leakage), non-canonical label rule (`sgpa<4.0`), schema alias mismatch. Do not reuse until corrected.
- M2 near-perfect R² reported as readiness — an **overclaim** that could mislead stakeholders. Must be re-derived on real data.
- `prediction_service.py` unbounded in-memory cache (no TTL) + synchronous predict inside async handlers.
- `requirements.txt` omits `asyncpg` (a runtime dependency of `prediction_service.py`).

### What is unclear / needs investigation (E)
- Whether any **real (non-synthetic)**, multi-cohort labeled dataset exists that v2 can train on. Everything hinges on this.
- Whether the external FastAPI service / live Supabase schema actually matches the CSV contracts used at training time (contract drift risk).
- Exact live production `GET /predict/insights` behavior (BLOCKED vs. served for M3/M2) against the real DB.
- `feature_data.py` SQL vs. live schema drift (CSE/BBA hardcoded).

---

## 7. Guardrail compliance
- ✅ Nothing deleted.
- ✅ No existing ML code modified.
- ✅ No retraining performed.
- ✅ No production model artifacts changed.
- ✅ No Supabase changes.
- ✅ No frontend/GenAI changes.
- ✅ No new models created.
- Only outputs: this audit + `ml_v2_architecture.md`.
