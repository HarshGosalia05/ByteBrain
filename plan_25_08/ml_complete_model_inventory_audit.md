# ByteBrain — Complete ML Model Inventory & Performance Audit

**Report ID:** `ML-MODEL-INVENTORY-AUDIT-2026-08-29`
**Auditor discipline:** STRICT READ-ONLY. No DB writes, no schema/ETL changes, no dataset rebuild, no retraining, no artifact overwrite, no prediction mutation, no code edits. Only loading artifacts/joblib (read), reading CSV/JSON, grepping code, and creating ONE report file: `plan_25_08/ml_complete_model_inventory_audit.md`. Temp verification was done in memory only.
**Purpose:** Definitive, verifiable inventory of EVERY ML model built/trained in the project (not just M1/M2/M3), with honest performance/leakage/readiness assessment. "Model exists" is kept strictly separate from "trained", "evaluated", "verified accuracy", and "production ready".

---

## 0. HOW TO READ THIS AUDIT (anti-confusion contract)

The five phrases used throughout are deliberately distinct:

| Phrase | Meaning | How verified |
|---|---|---|
| **Artifact exists** | A serialized model file is on disk | `Test-Path` / file listing |
| **Was trained** | A `fit()` ran and produced an artifact | training-script code + artifact load + training report timestamp |
| **Was evaluated** | CV/holdout metrics were computed | `evaluate.py` / `run_cv` code + report |
| **Has verified test accuracy** | A metric traced to THIS artifact's eval, not just train | report ↔ artifact cross-check (see each model) |
| **Production ready** | Deployed/served and withstands a validation gate | registry serving code + `ml_m3_validation_gate` verdict |

> Rule applied throughout: when a metric cannot be tied to the exact on-disk artifact, it is marked **NOT VERIFIED**, never assumed.

Adopted numbers are sourced from the project's own saved reports + the persisted artifact contents + live CSV snapshots. Where prior audit state contradicts a current number, the current code/artifact/CSV is authoritative.

---

## 1. DISCOVERY — EVERY ARTIFACT & ML ELEMENT IN THE PROJECT

### 1.1 All serialized model artifacts on disk (checked whole repo, excluding `.venv`, `__pycache__`, `node_modules`)

| Path | Size | Last modified | Stored type (verified by load) |
|---|---|---|---|
| `ml\artifacts\models\m1_subject_endmarks.joblib` | 441,234 B | 12-08-2026 23:24:44 | `dict` with `model` = `sklearn HistGradientBoostingRegressor`, `preprocess`, `feature_names` (12), `feature_tier`, `metadata` |
| `ml\artifacts\models\m2_next_semester_performance.joblib` | 570,857 B | 28-08-2026 16:06:08 | `dict` with 2 keys, each = `Pipeline(SimpleImputer → HistGradientBoostingRegressor)` (`next_semester_percentage`, `next_semester_sgpa`) |
| `ml\artifacts\models\m3_next_semester_at_risk.joblib` | 2,081 B | 14-08-2026 16:58:37 | `Pipeline(SimpleImputer → StandardScaler → LogisticRegression)` |

SHA-256 (recomputed this audit, unchanged vs prior task state):
- M1 `ml/artifacts/models/m1_subject_endmarks.joblib` = `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E`
- M2 `ml/artifacts/models/m2_next_semester_performance.joblib` = `6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012`
- M3 `ml/artifacts/models/m3_next_semester_at_risk.joblib` = `99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7`

**There is NO `m4_career_readiness.joblib`** — only the M4 score CSVs exist (`ml/data/final/m4_career_readiness_scores.csv` and `ml/m4_career_readiness_scores.csv`, 80 rows each, byte-equivalent modulo line endings).

### 1.2 All other built ML objects (not saved artifacts) and standalone ML code

| Element | Purpose | Trains? | Persists artifact? | Classification |
|---|---|---|---|---|
| `ml/src/m1/train_m1.py` | Canonical M1 trainer (baseline-first two-stage) | YES | YES → `m1_subject_endmarks.joblib` (line 179) | actual training |
| `ml/src/m1/evaluate.py`, `data.py`, `config.py` | M1 CV/data/config | — | no | support |
| `ml/src/m1/multi_holdout.py` | M1 temporal multi-window eval | trains transient | NO (line 20: existing M1 stays authoritative) | evaluation/report |
| `ml/src/m1/temporal.py` | M1 single hold-forward eval | trains transient | NO | evaluation/report |
| `ml/src/m1/readiness.py` | M1 artifact readiness/resubstitution | no | NO | verification |
| `ml/src/m2/train_m2.py` | M2 trainer (dict of pipelines) | YES | YES → `m2_….joblib` (line 83) | actual training (older path) |
| `ml/src/m2/data.py`, `evaluate.py`, `config.py` | M2 support | — | no | support |
| `ml/src/features/v1_m2_regression.py` | **V1 M2 regression trainer (current path)** | YES | YES → `m2_….joblib` (train_and_persist_m2, line 496) | actual training — produced the CURRENT M2 artifact |
| `ml/src/m3/train_m3.py` | M3 trainer (single pipeline) | YES | YES → `m3_….joblib` (line 79) | actual training (produced M3 artifact) |
| `ml/src/m3/data.py`, `evaluate.py`, `config.py` | M3 support | — | no | support |
| `ml/src/retrain_m3.py` | M3 feedback-informed retrain (offline, read-only DB) | YES (only if gate passes) | YES → `m3_….joblib` (line 536) | dormant/alternative M3 path |
| `ml/src/features/v1_baseline_m3.py` | LR baseline eval | trains transient in CV | NO | evaluation/report |
| `ml/src/features/v1_m3_experiment.py` | LR vs RF vs HGB controlled eval | trains transient | NO ("No production model persisted", line 35) | eval — RF/HGB **evaluated & discarded** |
| `ml/src/features/v1_model_improvement.py` | LR vs RF candidate | trains transient | NO | eval — RF **not promoted** |
| `ml/src/features/v1_m3_validation_gate.py` | Read-only gate | no | NO | verification |
| `ml/src/features/v1_m3_cohort_expansion.py`, `v1_later_cohort_gate.py`, `v1_feedback_audit.py`, `v1_etl_second_cohort_readiness.py` | pure analysis/verdicts | no | NO | analysis |
| `ml/src/features/v1_dataset.py`, `v1_cohort_dataset.py`, `v1_label_builder.py`, `v1_split*.py`, `v1_validation.py` | data/builders | no | NO | data prep |
| `ml/src/features/v1_ml_readiness_audit.py`, `v1_inference_contract.py` | contract/readiness | no | NO | verification |
| `ml/src/features/v1_config.py`, `v1_split_config.py` | config | — | no | config |
| `ml/src/m4/engine.py` | **M4 rule engine (deterministic, NOT ML)** | no | per build_m4 would write m4 joblib — **none exists** | rule engine |
| `ml/src/m4/build_m4.py` | serializes engine + writes score CSV | no | WOULD write `m4_career_readiness.joblib` (path defined) — **not on disk** | rule engine |
| `ml/src/m4/train_m4.py` | **legacy supervised M4 classifier** on `placement_readiness_level` | YES | YES → same `m4_career_readiness.joblib` path (collision) — **not on disk** | legacy model code only |
| `ml/src/m4/data.py`, `evaluate.py`, `config.py` | M4 support | — | no | support |
| `ml/m4_career_readiness.py` | standalone rule engine (duplicate) | no | NO (docstring: no joblib produced) | rule engine |
| `ml/src/m4_backup/*` | byte-identical copy of the old supervised M4 (pre-rule-engine) | (code) | no | legacy snapshot (code only) |
| `ml/files (1).zip` | unknown archive (16,548 B) | — | — | NOT extracted (read-only) |
| `ml/src/registry.py`, `inference.py`, `prediction_service.py`, `prediction_persistence.py`, `explain.py` | serving/contracts | no | no | serving (M4 = rule-based, no artifact) |

**Bottom line:** across the entire repo there are **exactly 3 serialized trained-model artifacts** (M1, M2, M3). All other "alternative/experimental/legacy" variants are code/report only and produced NO persisted artifact. The current M2 artifact was (re)trained by the M2/M3 cohort-expansion runner (`v1_m2_regression.train_and_persist_m2`) on 28-08-2026; M3's experimental RF/HGB are evaluated-and-discarded.

---

## SECTION A — MODEL ID / NAME / TYPE (per artifact)

### A.1 M1 — Subject Performance Predictor
- **Name:** `m1_subject_endmarks` (metadata: model=`m1_subject_endmarks`, version=1)
- **Artifact:** `ml/artifacts/models/m1_subject_endmarks.joblib`
- **Type:** dict artifact: `model` = **HistGradientBoostingRegressor**, `preprocess` = `[]` (no imputer/scaler needed for M1; SimpleImputer applied only if NaN present, not part of the stored preprocess list here), `feature_names` (12), `feature_tier`, `metadata`.
- **Existence:** EXISTS (441,234 B)
- **SHA-256:** `3404D29E…C6431E`
- **Trained:** metadata `trained_at = 2026-08-12T08:38:52Z`; file mtime 12-08-2026 23:24:44
- **Model version:** v1 (metadata)

### A.2 M2 — Next-Semester Performance Predictor
- **Name:** `m2_next_semester_performance`
- **Artifact:** `ml/artifacts/models/m2_next_semester_performance.joblib`
- **Type:** dict of 2 Pipelines, each `SimpleImputer(median) → HistGradientBoostingRegressor(max_iter=300, lr=0.1, depth=4, min_samples_leaf=10)`. Keys: `next_semester_percentage`, `next_semester_sgpa`.
- **Existence:** EXISTS (570,857 B)
- **SHA-256:** `6CAC9A88…E071C012`
- **Trained:** file mtime 28-08-2026 16:06:08 (this is the CSE+BBA expanded-cohort retrain via cohort expansion); contains NO metadata dict (metrics live in the reports, not the artifact). `n_features_in_=12` for both pipelines.
- **Model version:** not stored in artifact (implicit "expanded cohort" build)

### A.3 M3 — Next-Semester At-Risk / ATKT Predictor
- **Name:** `m3_next_semester_at_risk`
- **Artifact:** `ml/artifacts/models/m3_next_semester_at_risk.joblib`
- **Type:** single `Pipeline(SimpleImputer(median) → StandardScaler → LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42))`. `n_features_in_=12`. Classes `[0,1]`.
- **Existence:** EXISTS (2,081 B)
- **SHA-256:** `99D845FE…2044A7`
- **Trained:** file mtime 14-08-2026 16:58:37; NO metadata dict in artifact.
- **Model version:** not stored (implicit LogisticRegression baseline)
- **IMPORTANT caveat:** the artifact stores no metadata, and `ml/reports/m3_report.md` (mtime 12-08) predates the artifact (14-08), so the exact provenance/training-eval pairing of THIS artifact is **NOT fully verifiable** without retraining (read-only). It is a trained 12-feature LogisticRegression; its reported metrics must be treated with the caveats in §9/§10 (see Blocker).

### A.4 M4 — Career Readiness Scoring Engine
- **Name:** `m4_career_readiness` (registry `model_type = RULE_BASED`, `artifact_path = None`)
- **Artifact:** **NO `.joblib` EXISTS** (verified). Only score CSVs.
- **Type:** deterministic rule-based scoring engine (35 academic + 10 growth + 25 career + 30 lifestyle = 100; High ≥ 75, Medium ≥ 50). **NOT a trained ML model.**
- **Existence:** rule engine code exists (`ml/src/m4/engine.py` + standalone `m4_career_readiness.py`); outputs exist (2 CSVs). No artifact.

### A.5 Element count
- **Actual trained+persisted models:** 3 (M1, M2, M3)
- **Rule engine (no trained model):** 1 (M4)
- **Code-only trained-but-unpersisted / legacy / experimental variants:** M4 supervised classifier (`train_m4.py`), M3 RF/HGB candidates, M1 ridge/xgboost candidates, M2 ridge/xgboost candidates, `m4_backup` snapshot.

---

## SECTION B — WHAT EACH MODEL DOES (simple language)

### B.1 M1 — Predict a subject's end-of-semester exam marks
- **Problem:** While a semester is in progress (after internal/mid-sem marks and attendance are recorded, before the end-exam), score each subject.
- **About:** each (student, subject, semester) row.
- **Input:** internal marks, mid-sem marks, attendance %, subject type, credits, semester no, department, gender.
- **Output:** predicted `end_sem_marks` (0–70, clipped).
- **Type:** **regression** (continuous 0–70). Grain = student-subject-semester. Predicts a **future/current-in-progress** value (end of current semester T).

### B.2 M2 — Predict a student's next-semester performance
- **Problem:** from a completed semester T, predict performance in semester T+1.
- **About:** each (student, semester T) row with a T+1 outcome.
- **Input:** 9 semester-T aggregates (semester_no, subjects_registered, credits_registered, credits_earned, semester_total_marks, semester_percentage, semester_sgpa, semester_attendance_percentage, backlog_count) + department + gender.
- **Output:** two continuous targets: `next_semester_percentage` (0–100) and `next_semester_sgpa` (0–10).
- **Type:** **multi-target regression**. Predicts a **future** value (T+1).

### B.3 M3 — Predict whether a student will be at-risk next semester
- **Problem:** from a completed semester T, predict whether semester T+1 will be FAIL/ATKT or carry backlogs.
- **About:** each (student, semester T) row with a T+1 outcome.
- **Input:** same 9 semester-T aggregates + department + gender.
- **Output:** binary `is_at_risk_next_sem` (0/1).
- **Type:** **binary classification**. Predicts a **future** risk (T+1). NOTE: this is a *prediction* and must be kept separate from the deterministic `risk_predictions` register (explicitly labeled "future_risk_prediction" in explain contracts).

### B.4 M4 — Career readiness score
- **Problem:** holistic career-readiness score per student before placement season.
- **About:** each student (80).
- **Input:** academic avg %, attendance avg, previous backlogs, career preferences (domain/job/industry/work-mode/interests/certification/internship), lifestyle (study hours, attendance commitment, wellbeing, sleep, physical activity).
- **Output:** score 0–100 + level (Low/Medium/High) + positive/risk factor strings.
- **Type:** **deterministic rule-based scoring** (NOT ML). Predicts a **current** readiness state.

---

## SECTION C — TARGET / PREDICTION (exact)

| Model | Target column(s) | Target definition | Type | Unit | Horizon | Current or Future |
|---|---|---|---|---|---|---|
| M1 | `end_sem_marks` | subject-level end-exam marks (0–70); NULL = deployment | numeric | marks (0–70, clipped) | within semester T | Current-in-progress (future within T) |
| M2 | `next_semester_percentage` | `semester_percentage(T+1)` via `shift(-1)` per student | numeric | percent (0–100) | T+1 | Future |
| M2 | `next_semester_sgpa` | `semester_sgpa(T+1)` via `shift(-1)` per student | numeric | SGPA (0–10) | T+1 | Future |
| M3 | `is_at_risk_next_sem` | `(next_result(T+1) ∈ {FAIL, ATKT}) OR (next_backlogs(T+1) > 0)` | binary (0/1) | 1 = at-risk | T+1 | Future |
| M4 | `career_readiness_score` (+ `career_readiness_level`) | weighted rule sum (35/10/25/30), clipped 0–100 | numeric + categorical | score 0–100 (level Low/Med/High) | current | Current |
| M4 (legacy) | `placement_readiness_level` | synthetic survey target (Low/Med/High) | categorical | — | — | — (NOT served) |

M4 legacy supervised target `placement_readiness_level` is synthetic/derived from a survey snapshot; the served M4 does NOT use it (M4 served is the rule engine). Users are reminded: **a prediction from M2/M3 is not an actual academic value** — actual values live in `student_semester_summary`; predictions live append-only in `ml_predictions`.

---

## SECTION D — ALGORITHM (exact estimator classes)

Verified by loading the artifacts (read-only) and reading training scripts:

| Model | Final estimator | sklearn/XGB class | Notes |
|---|---|---|---|
| M1 | HistGradientBoostingRegressor | `sklearn.ensemble._hist_gradient_boosting.gradient_boosting.HistGradientBoostingRegressor` | candidates ridge/xgboost discarded; params max_iter=300, lr=0.1, depth=4, min_samples_leaf=10 |
| M2 (pct) | HistGradientBoostingRegressor | same class | inside `Pipeline(SimpleImputer → HistGBR)` |
| M2 (sgpa) | HistGradientBoostingRegressor | same class | same |
| M3 | LogisticRegression | `sklearn.linear_model.LogisticRegression` | inside `Pipeline(SimpleImputer → StandardScaler → LogisticRegression)`; class_weight="balanced", max_iter=1000, solver lbfgs |
| M4 | (none — rule function) | — | deterministic weights, no estimator |
| *M3 RF (candidate)* | RandomForestClassifier (n_est=200, depth=6, class_weight=balanced) — **eval-only, not persisted** | `sklearn.ensemble.RandomForestClassifier` | discarded |
| *M3 HGB (candidate)* | HistGradientBoostingClassifier (max_iter=200, lr=0.05, depth=5, class_weight=balanced) — **eval-only, not persisted** | `sklearn.ensemble.HistGradientBoostingClassifier` | discarded |
| *M4 legacy* | (would train LR/RF/HistGB classifier on placement level) — code only, no artifact | — | not served |

---

## SECTION E — ENSEMBLE METHOD (explicit, per model)

| Model | Bagging | Boosting | Stacking | Voting | Blending | RandomForest internal | Multiple models combined |
|---|---|---|---|---|---|---|---|
| M1 | NO | **YES (gradient boosting)** | NO | NO | NO | NO | NO (single HistGBR) |
| M2 pct | NO | **YES (gradient boosting)** | NO | NO | NO | NO | NO (single HistGBR) |
| M2 sgpa | NO | **YES (gradient boosting)** | NO | NO | NO | NO | — |
| **M2 (as a whole)** | NO | YES (each sub-regressor is GB) | NO | NO | NO | NO | **Partially — TWO parallel regressors (one per target) saved side by side; each is standalone, not a combined predictor**. Not stacking/voting — they output different quantities. |
| M3 | NO | NO | NO | NO | NO | NO | NO (single logistic model) |
| M4 | NO | NO | NO | NO | NO | NO | NO (rule function) |
| *M3 RF candidate* | **YES (RandomForest is bagging)** | NO | NO | NO | NO | YES | NO (but NOT persisted) |

**Important clarifications:**
- **Do NOT call RandomForest "stacking"** or HistGB "random forest". M2's two pipelines are parallel output heads (one per single target), not an ensemble that votes/combines; the only real "multiple models" is M2's two independent regressors for two different target quantities — that is multi-output modeling, NOT stacking/voting/blending.
- HistGradientBoosting **is** a boosting ensemble internally, so M1/M2 are boosting models. M3 is a plain (non-ensemble) classifier with a median imputer + standard scaler in front.
- RF/HGB M3 candidates were evaluated and **discarded**; no classifier other than logistic was persisted.

---

## SECTION F — DATA USED

### M1
- **Training dataset:** `ml/data/raw/student_subject_performance_rows.csv` joined 1:1 with `attendance_rows.csv` (on `enrollment_record_id`), `subjects_rows.csv` (on `subject_id`), `students_rows.csv` (on `student_id`). `ml/src/m1/data.py`.
- **Training rows:** 3,293 (end_sem_marks NOT NULL); **deployment rows:** 557 (NULL). **Students:** 80 (both train & deploy sets). CSE 2,453 / BBA 840 training (current CSV; corrected later to 2,450/840 per forensic audit, but the *current artifact* was trained on 3,293 incl. 3 stale Sem-7 rows — see §L).
- **Split:** no fixed train/test holdout — **GroupKFold(5) by `student_id` × 3 seeds** (student-isolated). No temporal hold-forward, but feature/target separation is strict (target = end_sem_marks, features exclude it).
- **Leakage prevention:** GroupKFold per student (zero overlap verified); forbidden columns list enforced (`m1/config.py:59-75`); target not in features; deployment rows excluded from training.
- **Future-semester info used:** NO (features are pre-end signals only; prior-history aggregates OFF, Stage B not run).

### M2
- **Training dataset:** current artifact from `v1_cohort_dataset.build_cohort_v1_dataset` / `v1_m2_regression` reading `student_semester_summary_rows.csv` + `students_rows.csv` (CSE + BBA, 80 students, 500 summary rows).
- **Training rows:** 420 (T+1 outcome present; CSE 300 sem1-6 + BBA 120 sem1-4); **deployment rows:** 80 (CSE sem7 + BBA sem5). **Students:** 80.
  - NOTE: the older `ml/reports/m2_report.md` (28-08 01:15) describes **CSE-only** (300 training/50 deploy). The current artifact (28-08 16:06) is the **expanded CSE+BBA** build (420/80). The authoritative expanded numbers are in `plan_25_08/ml_cohort_expansion_report.md`; the `ml/reports/m2_report.md` is now STALE relative to the artifact. This is a documented CSV-snapshot-vs-report version nuance.
- **Split:** GroupKFold(5) by `student_id`, seed 42, shared folds; deployment excluded; temporal via `shift(-1)`.
- **Leakage prevention:** targets = T+1 (strictly after feature snapshot); imputer fitted per-fold; deployment excluded; student isolation verified (`deployment_excluded_ok`, `student_isolation_ok` in code).

### M3
- **Training dataset:** same summary + students CSVs (current evaluation uses CSE+BBA cohort).
- **Current-eval rows:** 420 training (CSE+BBA) / 80 deployment; **positive rows** 28 (CSV snapshot) / 26 (live DB); **positive students** 6 (CSE 2, BBA 4).
  - Note: the artifact is a 12-feature LogisticRegression (2,081 B). It does NOT carry the cohort metadata, so whether the on-disk M3 was trained on 300 (CSE-only) or 420 (CSE+BBA) rows is **not recoverable from the artifact** (read-only). The `ml/reports/m3_report.md` (12-08) states class dist 392/28 = 420 rows → consistent with full-cohort reporting, but the artifact mtime (14-08) postdates that report.
- **Split:** GroupKFold(5) by student, seed 42 (gate reuses `v1_m3_experiment`).
- **Leakage prevention:** M3 target from T+1 outcome; deployment excluded; forbidden/leakage checks in `v1_config.V1_FORBIDDEN_COLUMNS`; no feedback as ground truth; no oversampling.

### M4
- **Dataset:** `students_rows.csv`, `student_semester_summary_rows.csv`, `career_preferences_rows.csv`, `lifestyle_survey_rows.csv` (per `m4_report.md`). 80 students scored.
- **Split/validation:** N/A (rule engine; evaluated on the full 80 as a distribution, no train/test).

---

## SECTION G — FEATURES (complete, per model)

### G.1 M1 — 8 raw features → 12 encoded columns
Raw (from `m1/config.py` BASELINE_RAW_FEATURES):
`internal_marks`, `mid_sem_marks`, `attendance_percentage`, `subject_type` (cat), `credits`, `semester_no`, `department_name` (cat), `gender` (bin).

Encoded (artifact `feature_names`, 12):
1. `internal_marks`
2. `mid_sem_marks`
3. `attendance_percentage`
4. `credits`
5. `semester_no`
6. `subject_type_Internship`
7. `subject_type_Laboratory`
8. `subject_type_Project`
9. `subject_type_Theory`
10. `department_name_BBA`
11. `department_name_CSE`
12. `is_male`

- **Raw columns:** 8 | **Engineered (encoded) columns:** 12 (4 categorical one-hot + 1 binary)
- **DB fields/tables:** `student_subject_performance` (internal_marks, mid_sem_marks, semester_no), `attendance` (attendance_percentage), `subjects` (subject_type, credits), `students` (department_name, gender). **5 tables** contributing.
- **Temporal:** all current-semester / pre-end signals; **no temporal leakage** (target excluded; no prior-history accepted).
- **INPUT FEATURES (encoded into estimator): 12.**

### G.2 M2 — 11 raw features → 12 encoded columns
Raw (`v1_split_config.FEATURE_COLUMNS`, same as `m2/config.py`):
`semester_no`, `subjects_registered`, `credits_registered`, `credits_earned`, `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_attendance_percentage`, `backlog_count`, `department_name`(cat), `gender`(bin).

Encoded (`ENCODED_FEATURE_COLUMNS`, 12; both M2 pipelines `n_features_in_=12`):
1. `semester_no`
2. `subjects_registered`
3. `credits_registered`
4. `credits_earned`
5. `semester_total_marks`
6. `semester_percentage`
7. `semester_sgpa`
8. `semester_attendance_percentage`
9. `backlog_count`
10. `department_name_BBA`
11. `department_name_CSE`
12. `is_male`

- **Raw columns:** 11 | **Engineered (encoded):** 12 | **DB tables:** `student_semester_summary` + `students` = **2 tables**.
- **INTPUT FEATURES: 12.**

### G.3 M3 — 11 raw → 12 encoded (identical contract)
Same 11 raw + same 12 encoded (`V1_FORBIDDEN_COLUMNS` excludes target/next-semester/feedback/student-id).
- **Raw columns:** 11 | **Encoded:** 12 | **DB tables:** `student_semester_summary` + `students` = **2 tables**.
- **INTPUT FEATURES: 12.**

### G.4 M4 — rule engine inputs (not a vectorized feature set)
Inputs consumed by the rule: `avg_semester_percentage`, `avg_semester_attendance`, `total_backlogs_computed` (academic); career-preferences booleans (internship, certification focus, forward-planning); lifestyle values (study hours, attendance commitment, wellbeing, stress, sleep, physical activity). These are business inputs to the rule, not an ML feature vector; no single fixed "feature count" is fed to an estimator. `feature_config.M4_FEATURES` documents a 13-field candidate list, but the served rule does not one-hot them into a model matrix. Legacy `train_m4.py` would one-hot career-preferences features (code only).

### G.5 IMPORTANT (leakage vs feature count)
IDs (`student_id`, `subject_id`, `enrollment_record_id`, `prediction_id`) are used only for grouping/traceability, **NOT passed to any estimator**. Targets and forbidden cumulative columns (`latest_sgpa`, `overall_*`, `total_backlogs`, `semester_result`, `next_*`, `placement_readiness_level`) are **never** in X. Metadat facts confirmed via `m1/config.py` FORBIDDEN, `feature_config.ALL_FORBIDDEN`, `v1_config.V1_FORBIDDEN_COLUMNS`.

---

## SECTION H — FEATURE IMPORTANCE / HIGH-WEIGHT FEATURES

**Global finding: feature importance is NOT persisted/calculated into any report or artifact for the served models (M1/M2/M3).** The only `feature_importances_`/`coef_` extraction code exists in the legacy M4 `train_m4.py`/`m4_backup` (writes a report, but that artifact is not on disk and M4 is not served). The ML-08 explainability report explicitly states feature_importance is `not_supported` (no SHAP, no stored weights). Therefore, for M1/M2/M3 the honest answer is:

> **NOT AVAILABLE** — feature importance was not persisted/calculated into any saved artifact or report for M1/M2/M3. (It could be extracted from the loaded estimators' `feature_importances_`/`coef_` at runtime, but no project artifact stores it.)

The sole exception I can responsibly report is the **M3 LogisticRegression coefficients, read directly from the loaded artifact (verifiable, not invented)**. Mapping the 12 encoded features to the loaded `coef_[0] = [2.1979, -1.7642, -0.0441, -1.2749, -0.9777, 0.2261, 0.0106, -0.1685, 2.193, 0.0, 0.0, -0.2934]` (unit-standardized scale, order = contract order):

| Rank | Encoded feature | Standardized coef | Direction (higher risk if positive) |
|---|---|---|---|
| 1 | `semester_no` | +2.198 | later semesters → more likely at-risk |
| 2 | `backlog_count` | +2.193 | more backlogs → at-risk |
| 3 | `subjects_registered` | −1.764 | more subjects → less likely at-risk |
| 4 | `credits_earned` | −1.275 | more credits earned → less risk |
| 5 | `semester_total_marks` | −0.978 | higher marks → less risk |
| 6 | `semester_sgpa` | −0.293 (is_male) / see below | — |
| 7 | `is_male` | −0.293 | male → slightly less risk |
| 8 | `semester_percentage` | +0.226 | (weak, counterintuitive direction) |
| 9 | `semester_attendance_percentage` | −0.169 | higher attendance → less risk |
| 10 | `credits_registered` | −0.044 | (weak) |

> Caveat: `department_name_BBA`, `department_name_CSE` = 0.0 (my note: if the artifact was trained CSE-only or with a zero-filled BBA column, the dept coef is uninformative). Because the exact M3 training cohort is unverifiable from the artifact, treat these coefficients as **indicative of the persisted model** but context-dependent. This is reported because it is read directly from a real weight vector — NOT business-invented.

**Distinguish "high feature importance" vs "business importance":** the small/underpowered M3 sample (§K/L) means even these coefficients are not trustworthy evidence of *business* driver importance; they describe the fitted baseline only.

---

## SECTION I — PERFORMANCE (verified metrics per model)

### I.1 M1 (verified against artifact metadata `stage_a` + report)
GroupKFold(5) × 3 seeds, student-isolated (CV = validation; no separate holdout): 

| Algorithm | MAE | RMSE | R² |
|---|---|---|---|
| ridge | 3.478±0.096 | 4.289±0.096 | 0.7651±0.1160 |
| **hist_gbm (selected, persisted)** | **3.181±0.110** | **3.837±0.102** | **0.8168±0.0819** |
| xgboost | 3.185±0.117 | 3.831±0.099 | 0.8168±0.0830 |

- Per-fold (hist_gbm, seed 0): MAE 3.204/3.067/3.162/3.100/3.371; R² 0.8247/0.8143/0.6707/0.8862/0.8881.
- These are **CV metrics**, the correct level for "how good is M1". Train-set resubstitution is not the headline. Save threshold MAE≤5.0 & R²≥0.7 satisfied → Stage B OFF.
- **Classification metrics: N/A (regression).**

### I.2 M2 (verified against expanded-cohort report matching current artifact)
GroupKFold(5) by student, seed 42; **expanded CSE+BBA (420 rows)**. (CSE-only 300-row numbers are in `ml/reports/m2_report.md` and the earlier regression report as a historical prior; the artifact is the expanded build.)

**`next_semester_percentage`** (train CV):

| model | MAE | RMSE | R² |
|---|---|---|---|
| ridge | ~15.0 | ~18.0 | ~0.63 |
| **hist_gbm (selected)** | **1.140 ± 0.125** (CSE-only 1.102±0.237) | — | ≈0.98 |
| xgboost | 1.361 ± 0.209 | — | — |

**`next_semester_sgpa`**:

| model | MAE | RMSE | R² |
|---|---|---|---|
| **hist_gbm (selected)** | **0.174 ± 0.018** | 0.274 (CSE-only) | ≈0.99 (CSE-only 0.9911±0.0092) |
| xgboost | 0.193 ± 0.030 | 0.259 | — |
| ridge | 0.201 (expanded) | — | — |

- Live-DB full run: hist_gbm pct MAE 1.065; sgpa MAE 0.177 (xgboost 0.1765 within noise — decision kept hist_gbm). R² high ≈0.98.
- These are **CV metrics** (GroupKFold). Being near-perfect, treat with small-sample caution (420 rows / 80 students). **Regression only.**

### I.3 M3 (metrics reported; must be read with BOTH the artifact-verifiability caveat AND the validation-gate BLOCK)
- `ml/reports/m3_report.md` (older, CSE-era) reports the persisted baseline: **Accuracy 1.000, Precision 0.800, Recall 0.800, F1 0.800, ROC-AUC 1.000** — this is the mean over GroupKFold(5) for the selected logistic model. It is a **reported** number; because the artifact stores no metadata and predates the report, **I cannot tie these numbers to the exact on-disk artifact without retraining. Mark `NOT VERIFIED` for this exact artifact.**
- Validation gate (`plan_25_08/ml_m3_validation_gate_report.md`, live DB, CSE+BBA 420 rows, 26 positives): reference logistic on informative folds (n=4) → prec 0.975, rec 1.000, F1 0.987, ROC-AUC 1.000, PR-AUC 1.000. Fold 2 = 0 positives (NaN, excluded). RF prec 0.933/rec 1.000/F1 0.964/AUC 1.000; HGB prec 0.975/rec 0.887/F1 0.923/AUC 0.998. **Gate verdict: FAIL (blocked)** — underpowered positive class.
- **Confusion/class dist:** 26–28 positive / 394–392 negative rows; 6 positive students; fold 2 has no positive validation example.

### I.4 M4 (rule engine)
No supervised accuracy — it is a deterministic scorer. Distribution over 80 students (report): Medium 46, High 19, Low 15; score range 13.15–94.41 (report) / 13.15–94.41 (CSV, mean ~64.3). Averages/High-Med-Low are descriptive, **not** classification accuracy. Persisted DB ml_predictions M4 distribution differs (36/31/13, avg 67.73) — a version/scope discrepancy, not a metric. **No model accuracy to report (rule engine).**

---

## SECTION J — PREDICTION EXAMPLES (only from real outputs; none modified)

- **M1 deployment sample** (from `train_m1.py` prediction-test printout, 12-08): deployment rows show predicted `end_sem_marks` distribution min/mean/max over 557 rows (the trained run printed row-level predicted marks for the first 10 deployment rows, e.g. STU000002 sem7 etc.). Because these were console-printed during training, they are historical logs — treat as illustrative, not a persisted table.
- **M2:** predicted next-semester SGPA/percentage are served to `ml_predictions` (append-only). 5,072 prediction rows total (all models). No ground-truth-yet for the live-semester T+1 (deployment rows), so "was the prediction correct" is **NOT VERIFIED** (future outcomes not yet observed for the served predictions).
- **M4:** CSV `ml/data/final/m4_career_readiness_scores.csv`, e.g.:
  - STU000033 (Meet Patel, CSE Sem7): avg pct 95.04 → score 94.41 → **High**.
  - STU000023 (Diya Desai, CSE Sem7): avg pct 94.3 → score 93.82 → **High**.
  - These are deterministic rule scores, not ML predictions; correctness is by construction (weighted sum).

---

## SECTION K — MODEL READINESS

| Model | Readiness | Why |
|---|---|---|
| **M1** | **READY WITH CONDITIONS** | Trained + CV-evaluated (MAE 3.18, R² 0.82, student-isolated). Conditions: (1) artifact was trained on 3,293 CSV rows that include 3 stale/fabricated CSE Sem-7 end-sem rows (forensic audit) → target contamination; (2) STU000002's genuine subject is SUB0053, CSV wrongly carried SUB0050=40; (3) re-derive on cleaned 3,290 before relying on it; (4) no true held-out test split (GroupKFold only → point estimate, no year-shift). Until cleaned retrain, "verified accuracy" is on the contaminated dataset. |
| **M2** | **READY WITH CONDITIONS** | Trained + CV-evaluated on expanded CSE+BBA (420 rows), near-perfect CV metrics, temporal/student isolation confirmed. Conditions: (1) target rows at T come from the *current* CSV whose T+1 summaries include **fabricated/zeroed live-semester** outcomes (Sem-7 CSE per forensic audit); (2) even though the split is target-driven and self-excludes NULL-live rows, the current CSV has fabricated non-NULL live summaries, so those 80 boundary rows are **invalid labels** (placeholder values, not actuals); (3) a clean rebuild should NULL the 80 live rows and re-derive → correct boundary self-exclusion; (4) no held-out department/year split; near-perfect R² should be read with small-sample caution. Not production-proven on a true hold-forward. |
| **M3** | **BLOCKED** | Independent of the data correction, the **positive class is statistically underpowered** (6 positive students, 1 of 5 folds has 0 positives) → validation gate verdict **FAIL (blocked)**. Reported "Accuracy 1.000 / F1 0.8/0.987" is a clean-separation/small-sample artifact, NOT production evidence. Do NOT promote RF/HGB; do NOT integrate into API/dashboard while underpowered. Also, the current CSV's fabricated live-semester labels contaminate the target derivation. |
| **M4** | **PRODUCTION READY (as a rule engine)** | Not an ML model; deterministic, no training, no data-dependence beyond real inputs. Serve-ready. Note: it must NOT be called an ML model; M4 supervised classifier (code) is NOT served and shares a collision-prone artifact path. |

---

## SECTION L — DATA LEAKAGE (per model)

| Check | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| Target leakage | NO (target excluded; forbidden enforced) | NO (targets = T+1, excluded from X) | NO (target = T+1 outcome-derived) | N/A (rule) |
| T+1 contamination | N/A (target is end of current sem) | **YES-risk: 80 boundary rows labeled by fabricated/zeroed live summaries** | **YES-risk: SAME 80 boundary rows** | N/A |
| Future-semester info used | NO | Only explicit T+1 target, not as feature | Only T+1 target sources, not features | academic aggregates across all sems (acceptable for readiness) |
| Incomplete semesters included | Deployment rows excluded from training; training rows are subject-level | Live (Sem7/5) rows currently in X if present in CSV; targets for them are placeholder | Live rows in X; labels placeholder | yes (all semesters) — fine for rule |
| Seeded/fabricated values included | **3 stale/fabricated Sem-7 end-sem rows in training** | **80 fabricated/zeroed live-semester labels** (current CSV) | **fabricated live-semester labels (28 vs 26 live)** | synthetic snapshot values exist but used only as rule inputs |
| Prediction reused as actual input | NO | NO | NO (explain label separates future-risk prediction from risk register) | NO |
| Forbidden columns used | NO (checked) | NO | NO (`V1_FORBIDDEN_COLUMNS`) | NO |
| Student-identity leakage | NO (GroupKFold by student; student_id never a feature) | NO | NO | N/A |
| Train/test student overlap | NO (isolated) | NO | NO | N/A |
| Temporal overlap | NO (target-based) | NO (T+1 boundary) | NO | N/A |

**LEAKAGE STATUS:**
- **M1 = CONFIRMED RISK (target/label contamination):** 3 fabricated Sem-7 end-sem rows are in its current training set — not a leak of future info into a current-feature (features are clean), but a **label-quality** issue (fabricated targets).
- **M2 = CONFIRMED (target-label contamination at boundary):** 80 rows' T+1 targets are fabricated/zeroed live-semester summaries (current CSV). The split logic *would* self-exclude if those were NULL, but the current CSV holds non-NULL placeholder values → invalid supervision.
- **M3 = CONFIRMED (target-label contamination):** same 80 boundary rows + CSV-vs-live drift (28 vs 26 positives). PLUS statistical underpowering ("BLOCKED").
- **M4 = CLEAN (rule engine).**

---

## SECTION M — DATABASE TABLES USED (per model)

| Model | Table | Columns used | Purpose |
|---|---|---|---|
| M1 | `student_subject_performance` | student_id, subject_id, semester_no, internal_marks, mid_sem_marks, end_sem_marks(target), enrollment_record_id | subject facts + target |
| M1 | `attendance` | enrollment_record_id, attendance_percentage | attendance feature |
| M1 | `subjects` | subject_id, subject_type, credits | subject-type + credits features |
| M1 | `students` | student_id, department_name, gender | metadata features |
| M1 | `student_subject_enrollment` | student_id, subject_id (via prediction-service SQL join) | serving-join source |
| M2 | `student_semester_summary` | student_id, semester_no, subjects_registered, credits_registered, credits_earned, semester_total_marks, semester_percentage, semester_sgpa, semester_attendance_percentage, backlog_count, semester_result (target source), semester_grade | features + targets |
| M2 | `students` | student_id, department_name, gender | metadata features |
| M3 | `student_semester_summary` | same as M2 (+ semester_result, backlog_count as target sources) | features + target |
| M3 | `students` | student_id, department_name, gender | metadata features |
| M4 (rule) | `students` | student_id, enrollment_no, full_name, department_name, current_semester, gender | identity/context |
| M4 (rule) | `student_semester_summary` | semester_no, semester_percentage, semester_attendance_percentage, backlog_count | academic aggregates |
| M4 (rule) | `career_preferences` | preferred_domain, dream_job_role, preferred_industry, preferred_work_mode, higher_studies_interest, entrepreneurship_interest, certification_interest, internship_completed | career inputs |
| M4 (rule) | `lifestyle_survey` | daily_study_hours, attendance_commitment, mental_wellbeing, stress_level, average_sleep_hours, physical_activity | lifestyle inputs |

- **Columns actually consumed by the estimator:** M1 = 12 encoded (from 8 raw across 5 tables); M2 = 12 encoded (from 11 raw across 2 tables); M3 = 12 encoded (from 11 raw across 2 tables); M4 = rule inputs (not a vector).
- **TOTALS:** DB tables **directly used** = M1:4 (+1 serving join), M2:2, M3:2, M4:4. DB columns used (distinct estimator features) ≈ M1 12, M2 12, M3 12 (encoded), M4 ~14 rule inputs.
- Tables *inspected by scripts but not consumed by a model* (e.g., `departments_rows.csv`, `users`, `faculty`) are NOT counted per the instruction.

---

## SECTION N — PIPELINE (per model)

**M1:** CSV `student_subject_performance_rows` → `m1/data.build_dataset` (1:1 joins) → one-hot encode (`m1/data.one_hot_encode`) → GroupKFold(5)by-student CV over ridge/hist_gbm/xgboost (`m1/evaluate.run_cv`) → select best → `fit_final` → `joblib.dump` → `m1/train_m1.py:179` → artifact dict → reload → prediction via `inference.predict_m1` → `prediction_service.predict_m1_for_student` (DB fetch) → `prediction_persistence` → `ml_predictions`.

**M2:** summary+students CSV → `v1_cohort_dataset` (CSE+BBA) → `v1_m2_regression.build_m2_regression_frames` (shift(-1) T+1) → one-hot 12-col → GroupKFold(5) CV → select (min MAE) → `train_and_persist_m2` fits 2 pipelines → artifact dict → serving `inference.predict_m2` → `prediction_service` → `ml_predictions`.

**M3:** summary+students CSV → `v1_cohort_dataset` → M3 target `is_at_risk_next_sem` → one-hot 12-col → `v1_m3_experiment` GroupKFold(5) LR-vs-RF-vs-HGB (eval only) → gate (`v1_m3_validation_gate`) → persisted baseline = `m3/train_m3.py` pipeline (or `retrain_m3`) → `inference.predict_m3` → serving → `ml_predictions`.

**M4:** students+summary+career+lifestyle → `ml/src/m4/engine.py CareerReadinessEngine.score()` (deterministic) → score CSV → `inference.predict_m4` (loads engine) → `prediction_service` → `ml_predictions`. No training stage.

---

## SECTION O — TRAINING STATUS

| Model | Actually trained? | When | Dataset | Success | Artifact saved | Loaded for inference | Currently served? | Stale? |
|---|---|---|---|---|---|---|---|---|
| M1 | YES | 12-08-2026 | 3,293 rows (student_subject_performance + joins) | YES (metadata, report) | YES (441 KB) | YES (`inference.predict_m1`) | YES | **STALE-ISH** (3 fabricated rows; housekeeping needed) |
| M2 | YES | artifact 28-08-2026 (expanded); first trained earlier (CSE-only) | 420 rows CSE+BBA (current) / 300 (older) | YES | YES (570 KB dict of 2) | YES (`inference.predict_m2`) | YES | CURRENT build is expanded; boundary-label fabrications remain in source CSV (ML-forensic issue) |
| M3 | YES | artifact 14-08-2026 (12-feature LR) | reported 420 rows (or earlier CSE 300 — not artifact-verifiable) | YES (artifact loads) | YES (2 KB LR) | YES (`inference.predict_m3`) | Served but **BLOCKED** in gate/contract | YES — underpowered; gate FAIL |
| M4 | N/A (rule) | N/A | 80 students | N/A | NO artifact | YES (engine instantiated) | YES | N/A |

---

## SECTION P — MODEL COMPARISON TABLE

| Model | Exists | Actually Trained | Problem | Target | Algorithm | Ensemble | Train Rows | Features | DB Tables | Test Metric | Best Verified Metric | Leakage | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | YES | YES | subject end-mark regression | `end_sem_marks` (0–70) | HistGBR | boosting | 3,293 | 12 | 4(+1) | GroupKFold(5)×3 (CV) | MAE 3.181 / R² 0.817 | **CONFIRMED label-contamination** (3 stale rows) | READY W/ CONDITIONS |
| M2 | YES | YES | next-sem performance | `next_semester_pct`/`sgpa` | 2× HistGBR | boosting (eac) | 420 (exp.) | 12 | 2 | GroupKFold(5) (CV) | MAE pct 1.14 / sgpa 0.174 / R²≈0.98 | **CONFIRMED boundary-label contamination** (current CSV) | READY W/ CONDITIONS |
| M3 | YES | YES | next-sem at-risk | `is_at_risk_next_sem` | LogisticRegression | none | 420 (reported) | 12 | 2 | GroupKFold(5) (CV) + gate | reported Acc 1.000 / F1 0.8; gate issued FINAL 0.987 | **CONFIRMED boundary-labels + underpowered** | **BLOCKED** |
| M4 | rule only | N/A | career readiness | score 0–100 | deterministic rules | none | — | ~14 rule inputs | 4 | N/A | rule distribution (no accuracy) | CLEAN | READY (rule) |
| *M3 RF (cand)* | no | eval only | — | same | RFC | bagging | 420 | 12 | 2 | CV | F1 0.964 (gate) | — | discarded/not promoted |
| *M3 HGB (cand)* | no | eval only | — | same | HistGBC | boosting | 420 | 12 | 2 | CV | F1 0.923 (gate) | — | discarded/not promoted |
| *M4 legacy* | no artifact | code only | placement level | `placement_readiness_level` | (LR/RF/HistGB) | — | — | — | — | — | — | — | code only, not served |

---

## SECTION Q — M1/M2/M3 SPECIFIC AUDIT

### Q.1 M1
1. Exact name: `m1_subject_endmarks` | 2. Artifact: `ml/artifacts/models/m1_subject_endmarks.joblib` | 3. Algorithm: HistGradientBoostingRegressor | 4. Bagging: NO | 5. Boosting: YES | 6. Stacking: NO | 7. Target: `end_sem_marks` (0–70) | 8. Prediction: predicted end-exam marks per subject in current semester | 9. Train rows: 3,293 (80 students) | 10. Input features: 12 | 11. DB tables: 4 (+1 serving join) | 12. DB columns: 12 encoded | 13. Top-10 important: **NOT AVAILABLE** (not persisted) | 14. Accuracy: N/A (regression) | 15–18. Precision/Recall/F1/ROC-AUC: N/A | 19. MAE/RMSE/R²: CV MAE 3.181, RMSE 3.837, R² 0.817 | 20. Validation: GroupKFold(5) by student ×3 seeds (CV) | 21. Leakage: label-contamination (3 fabricated rows) | 22/23. Readiness reason: READY WITH CONDITIONS (cleaned-data retrain + honest small-sample caveat).

### Q.2 M2
1. `m2_next_semester_performance` | 2. `ml/artifacts/models/m2_next_semester_performance.joblib` | 3. 2× HistGradientBoostingRegressor (per target) | 4. Bagging NO | 5. Boosting YES | 6. Stacking NO | 7. Targets: `next_semester_percentage`, `next_semester_sgpa` | 8. Predicts next-semester pct & SGPA from current-semester summary | 9. Train rows: 420 (expanded; 300 older) | 10. Input features: 12 | 11. DB tables: 2 | 12. DB columns: 12 encoded | 13. Top-10 features: NOT AVAILABLE | 14. N/A (regression) | 15–18. N/A | 19. MAE pct 1.140 / sgpa 0.174, R²≈0.98 | 20. GroupKFold(5) by student (CV) | 21. Leakage: boundary-label contamination in current CSV | 22/23. READY WITH CONDITIONS (rebuild after NULL-ing fabricated live summaries + year-shift validation).

### Q.3 M3
1. `m3_next_semester_at_risk` | 2. `ml/artifacts/models/m3_next_semester_at_risk.joblib` | 3. LogisticRegression | 4–6. Bagging/Boosting/Stacking: NO/NO/NO | 7. Target: `is_at_risk_next_sem` | 8. Predicts binary at-risk next semester | 9. Train rows: reported 420 (artifact not self-documenting) | 10. Input features: 12 | 11. DB tables: 2 | 12. DB columns: 12 | 13. Top-10: coefficients read from artifact (semester_no +2.20, backlog +2.19, subjects −1.76, credits_earned −1.27…) — NOT a persisted importance file | 14. Accuracy reported 1.000 (m3_report) — **NOT VERIFIED for this exact artifact** | 15. Precision 0.800 (report) / 0.975 (gate) | 16. Recall 0.800 (report) / 1.000 (gate) | 17. F1 0.800 (report) / 0.987 (gate) | 18. ROC-AUC 1.000 (report/gate) | 19. N/A (classification) | 20. GroupKFold(5) by student + validation gate | 21. Leakage: fabricated live-semester boundary labels + CSV/live drift + underpowered positive class | 22/23. **BLOCKED** — validation gate FAIL (6 positive students, fold 2 uninformative); do not integrate/promote; add a second independent cohort before advancing.

---

## SECTION R — OTHER MODELS (all variants found)

| Variant | Trained? | Artifact? | Notes |
|---|---|---|---|
| M4 rule engine | no (deterministic) | NO artifact | service uses it; label "NOT ML" |
| M4 supervised classifier (`train_m4.py`) | code (ran before to F1 0.975 train-set per `.bak` report) | NO on disk | shares path `m4_career_readiness.joblib` with rule engine → **collision risk**; discriminates Low/Medium (synthetic label) |
| M4 legacy `m4_backup` | identical code snapshot | none | duplicate of old supervised M4 |
| M1 ridge / xgboost candidates | trained transiently in CV | NO | discarded (hist_gbm won) |
| M2 ridge / xgboost candidates | trained transiently | NO | discarded (hist_gbm won) |
| M3 random_forest / hist_gbm candidates | trained transiently | NO | evaluated, NOT promoted |
| M1 multi_holdout/temporal/readiness | eval only | NO | no artifact written |
| retrain_m3 (feedback) | dormant alternative M3 trainer | would write m3 artifact | gated/dormant |

All confirm: **only 3 real trained artifacts; everything else is code/report/transient.**

---

## SECTION S — ACCURACY CLARIFICATION (per model, explicit 5-way)

| Model | Artifact exists | Was trained | Was evaluated | Has verified *test* accuracy (tied to artifact) | Production-ready |
|---|---|---|---|---|---|
| M1 | TRUE | TRUE | TRUE | TRUE (CV metrics in artifact metadata, matching trained artifact) — regression MAE/R² | Conditional (needs cleaned-data retrain + holdout caveat) |
| M2 | TRUE | TRUE | TRUE | TRUE for the expanded cohort (metrics in cohort report matching artifact); older `ml/reports/m2_report.md` is STALE vs artifact → for THAT report: NOT VERIFIED | Conditional (boundary-label rebuild + year-shift validation) |
| M3 | TRUE | TRUE | TRUE (CV + gate) | **NOT VERIFIED for the exact artifact** (report predates artifact mtime; no artifact metadata); gate metrics are eval-only reference-baseline numbers | **NO — BLOCKED** (gate FAIL) |
| M4 | FALSE (no artifact) | N/A (rule) | N/A | N/A (no model accuracy; deterministic) | YES as a rule engine |

Clarifying the distinction risks precisely: the most dangerous trap in this project is **M3**, where "artifact exists + report says Accuracy 1.000" could be mistaken for "production-ready". It is not: the "1.000" is a small-sample clean-separation artifact, the exact artifact's eval is not verifiable from the artifact itself, and the validation gate returned BLOCKED. Likewise **M1/M2** artifacts exist and were evaluated, but were trained on data containing fabricated live-semester labels, so their "verified" metrics measure on a contaminated target space; a cleaned retrain is required before relying on them.

---

## SECTION T — FINAL HUMAN-READABLE ANSWER

**Right now your project has 3 actual trained ML models (M1, M2, M3) and 1 scoring engine (M4) that is NOT an ML model.**

**1. M1 — Subject Performance Predictor**
- What it does: predicts a subject's end-of-semester exam marks (0–70) while the semester is still going, using internal/mid-sem marks + attendance.
- Algorithm: Gradient Boosted Trees (HistGradientBoostingRegressor).
- Bagging/Stacking/Boosting: **Boosting** (not bagging, not stacking).
- What it predicts: end-exam marks per subject.
- Uses **12 features from ~5 DB tables** (students, student_subject_performance, attendance, subjects, +enrollment join).
- Most important features: **Not saved** (would need to pull from the model at runtime). Real drivers are internal/mid marks and attendance.
- Verified performance: **CV MAE 3.18 / RMSE 3.84 / R² 0.82** (GroupKFold by student). That is honest; it's the CV number, not training-set.
- Current status: **Ready with conditions** — useful, but it was trained on data containing 3 stale/fabricated Sem-7 rows; needs a cleaned rebuild and is not yet proven on a truly held-out year.

**2. M2 — Next-Semester Performance Predictor**
- What it does: predicts a student's next-semester percentage and SGPA from the current semester.
- Algorithm: Gradient Boosted Trees (two of them, one per target).
- Ensemble: each is **Boosting**; the two regressors are separate output heads, **not** stacking/voting.
- What it predicts: next-semester percentage (0–100) and SGPA (0–10).
- Uses **12 features from 2 DB tables** (student_semester_summary, students).
- Most important features: **Not saved**.
- Verified performance: **CV MAE ~1.14 (pct) / ~0.17 (SGPA), R² ~0.98** on the 420-row CSE+BBA cohort. These are *very* good but on a small sample.
- Current status: **Ready with conditions** — has near-perfect CV numbers but the target rows include fabricated/zeroed live-semester values in the current CSV; needs the data cleaned (NULL the 80 fake live outcomes) and a year-shift validation before I'd fully trust it.

**3. M3 — Next-Semester At-Risk Predictor**
- What it does: predicts whether a student will be at-risk (FAIL/ATKT/backlog) next semester.
- Algorithm: Logistic Regression (baseline).
- Ensemble: **none** (plain single classifier).
- What it predicts: 0/1 at-risk flag for next semester.
- Uses **12 features from 2 DB tables** (same as M2).
- Most "important" (from the model's weights): semester_no and backlog_count push risk up; subjects_registered and credits_earned pull it down. These are read from the loaded model, not a saved importance file — treat as indicative only.
- Reported accuracy: **the "Accuracy 1.000" in old reports is NOT trustworthy for this artifact** — I couldn't verify the exact artifact's evaluation, and the project's own validation gate says the model is **BLOCKED** because there are only 6 at-risk students and one fold has no at-risk examples. Perfect scores here are a small-data illusion, not proof.
- Current status: **BLOCKED**. Don't ship or rely on it until a second cohort adds enough real at-risk students.

**4. M4 — Career Readiness Score Engine**
- What it does: gives each student a 0–100 career-readiness score and a Low/Medium/High band.
- Algorithm: **none** — it's a fixed set of business rules (academic 35 + growth 10 + career 25 + lifestyle 30).
- Bagging/Stacking/Boosting: **none**.
- What it predicts: a current readiness score (not a future prediction).
- Uses ~14 inputs from 4 tables (students, summaries, career_preferences, lifestyle_survey).
- Most important factors: academic record (35 pts), career prep (25), lifestyle (30), growth (10) — these are the rule weights.
- Verified performance: **no ML accuracy** (it's deterministic). Output: Medium 46 / High 19 / Low 15 over 80 students.
- Current status: **Safe to use as-is** (it's rules, not learned). Just don't call it an AI model.

---

### Plain-language summary

- **Strongest / safest to use:** **M4** (rule engine — deterministic, no data trap) and **M2** (best real ML regressor, near-perfect CV, but re-train on cleaned data first).
- **Weakest / most dangerous:** **M3** — its impressive-sounding "100% accuracy" is misleading; it is statistically underpowered and BLOCKED.
- **Blocked:** **M3** (validation gate FAIL — too few at-risk students).
- **Needs retraining:** **M1, M2** (they were trained on data with fabricated live-semester rows; rebuild after correcting/NULL-ing the 80 fake live-semester summaries), and **M3** (needs more real at-risk students, not just a re-run).
- **Can the reported accuracy be trusted?** Only M1's and M2's CV numbers can be traced to their artifacts, and even those are on slightly contaminated source data. M3's "1.000" is not verifiable for the exact artifact and is not production evidence. So: **treat M1/M2 numbers as good-but-to-be-re-derived, and do not trust M3's reported accuracy.**
- **What to fix / train next:** (1) clean the data (NULL the 80 fabricated live-semester summaries, drop the 3 stale M1 rows) and rebuild M1 (3,290), M2 (340), M3 (340-valid, still gated); (2) add a **second independent academic-year cohort of at-risk students** so M3's positive class becomes well-powered; (3) add a year-hold-forward validation so M1/M2 aren't just student-grouping CV; (4) resolve the M4 `train_m4.py`/`build_m4.py` shared-artifact-path collision (rule engine vs supervised classifier).

---

## SECTION U — VERIFICATION LOG (what was checked vs what could NOT be verified)

**Verified (read-only, on disk / code / CSV):**
1. Every `.joblib` in the repo = exactly M1/M2/M3; all hashes recomputed and unchanged.
2. Artifact internals loaded: M1=HistGBR dict(12f), M2=2×HistGBR pipelines(12f), M3=LogReg pipeline(12f, classes[0,1]).
3. CSV row counts: summary 500, students 80, performance 3850 (501/81/3851 lines incl. header).
4. Feature lists against training/inference code (`m1/config`, `v1_split_config`, `feature_config`, `v1_config`).
5. DB tables/columns against `feature_config.M2M3_FEATURES`, `V1_BASE_QUERY`, `prediction_service` SQL.
6. Ensemble classification against actual estimator/pipeline objects (no stacking/voting; boosting for M1/M2; none for M3; bagging only in discarded RF).
7. Route-M2 artifact = expanded-cohort build (mtime 28-08 + cohort report) — older `ml/reports/m2_report.md` is stale vs artifact.
8. M4 has NO trained artifact; legacy M4 classifier shares path (collision) but is code-only.
9. `git status` — the only model-file change shown is the **pre-existing** uncommitted `ml/artifacts/models/m2_next_semester_performance.joblib` (from the cohort-expansion retrain). **This audit made NO file/db/prediction changes.**

**Could NOT be verified (honest list):**
1. Exact training cohort/provenance of the **current M3 artifact** (no artifact metadata; `m3_report.md` predates artifact mtime). Its reported accuracy is therefore marked NOT VERIFIED.
2. A held-out test set / genuine accuracy for any model — only GroupKFold CV and eval-gate metrics exist (no saved holdout test split for M1/M2; M3 has no production test).
3. Feature importance for M1/M2 (never persisted); only M3 coefficients read directly from the loaded artifact.
4. "Was the served prediction correct" for live-semester predictions (future ground truth not yet observed).
5. Whether the 3 stale M1 rows / 80 fabricated live-semester rows were already corrected in the live DB — the CSVs (training inputs) still contain them; DB correction is a separate, not-run step (this audit is read-only and deliberately does not correct).
6. `ml/files (1).zip` contents (not extracted, read-only).

**Safety final:** "NO DATABASE, CSV, DATASET, MODEL, PREDICTION RECORD, MIGRATION, OR PROJECT CODE WAS MODIFIED. Only `plan_25_08/ml_complete_model_inventory_audit.md` was created."
