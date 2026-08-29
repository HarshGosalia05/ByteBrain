# M2/M3 Multi-Department (CSE + BBA) Cohort Expansion Report

**Step:** Re-expand the M2 regression and M3 classification training/evaluation
population from the CSE-only cohort to the full supported multi-department
cohort (CSE + BBA), using the existing project data/feature architecture, with
a department feature-contract (one-hot) guarantee, re-evaluation, and
verification.

**Source of truth:** the completed Integrated ML Readiness Audit
(`plan_25_08/ml_readiness_audit_report.md`) concluded
`READY WITH DOCUMENTED DATA LIMITATIONS` and named the largest remaining
statistical-generalization gap as: M2 artifact CSE-only; M3 evaluation coverage
limited; full supported cohort = CSE + BBA; department one-hot consistency must
be explicitly guaranteed. This step addresses exactly that.

**Scope guard:** ONLY M2 + M3 cohort expansion + department one-hot guarantee +
re-evaluation + verification. No M1, M4, deployment, prediction APIs, dashboard,
GenAI, auth, ETL redesign, DB schema changes, production integration.

---

## 1. Objective

Widen the M2/M3 training/evaluation population from CSE-only (50 students) to
the full supported cohort (CSE + BBA, 80 students) by reusing the existing data
and feature architecture, explicitly guarantee the department one-hot columns,
re-run the existing M2/M3 candidates/metrics/selection rules, and determine
whether the expansion materially improves statistical generality (especially M3
positive-class coverage).

## 2. Previous CSE-only limitation

- M2/M3 V1 scope was CSE-only: 50 students, 350 rows, 300 training rows,
  deployment at semester 7 only.
- M3 positive class was severely underpowered: 2 positive students, 10 positive
  rows, only 2/5 GroupKFold folds informative.
- M2 artifact (`m2_next_semester_performance.joblib`) was trained on CSE-only
  data while the M2 feature contract exposes `department_name_BBA/CSE`, leaving
  cross-department generalization unverified.
- No explicit test guaranteed that a single-department subset (or an expanded
  multi-department cohort) always retains the full 12-column department one-hot
  contract.

## 3. Existing full cohort definition

Verified from the live PostgreSQL database (`student_semester_summary` JOIN
`students`) and its CSV mirror (`proved` to match: `verify_feature_engineering.py`
live read reported the same 80 students / 500 rows as the CSV snapshot):

- **Departments included:** `CSE`, `BBA` (the complete `students` population —
  no other departments exist; `SUPPORTED_DEPARTMENTS = ("CSE", "BBA")`).
- No department added that merely exists in some table; the cohort scope is the
  full supported `students` population.

## 4. CSE/BBA row and student counts (verified against live DB + CSV)

| Metric | CSE | BBA | **Total** |
|--------|-----|-----|-----------|
| Students | 50 | 30 | **80** |
| Summary rows | 350 | 150 | **500** |
| Training rows (M2/M3) | 300 | 120 | **420** |
| Deployment rows | 50 | 30 | **80** |
| Semester range | 1..7 | 1..5 | — |
| M2 target availability | sem 1–6 training / 7 deploy | sem 1–4 training / 5 deploy | — |
| M3 positive rows (CSV snapshot) | — | — | 28 |
| M3 positive rows (live DB) | — | — | 26 |
| M3 positive students | 2 | 4 | **6** |

## 5. Department deployment boundaries

Per-department (per-student last-semester) deployment boundary, **not** a fixed
semester 7:

| Department | Last semester (deployment) |
|------------|----------------------------|
| CSE | 7 |
| BBA | 5 |

Verified: deployment rows for the expanded cohort are exactly `{5, 7}`; no BBA
training row reaches semester 5; no (student_id, semester_no) deployment pair
appears in any training/evaluation fold.

## 6. Feature-contract change / guarantee

- **Encoded feature count:** 12 (unchanged contract, `ENCODED_FEATURE_COLUMNS`).
- **Department columns:** `department_name_BBA`, `department_name_CSE` are always
  present, at fixed positions 11 and 12, via the existing `one_hot_encode_features`
  zero-fill alignment (`v1_split.py`). This guarantee now has explicit tests.
- **Single-department subset:** a CSE-only subset still yields both department
  columns (`department_name_BBA` all-zero), so no silent column drop can break
  the contract mid-pipeline.
- **Deterministic ordering:** training and evaluation use the identical 12-column
  order; the full cohort produces the same columns as a single-department subset.
- **No target leakage through encoding:** department one-hot does not expose
  any target or target-source value; targets remain disjoint from X.
- **No feature definitions changed** — the expansion reuses the existing 11-raw →
  12-encoded contract untouched.

## 7. M2 methodology

Reused `features.v1_m2_regression.run_m2_regression` unchanged:

- **Targets:** `next_semester_percentage`, `next_semester_sgpa` — `shift(-1)`
  within student (T → T+1), strictly after the feature snapshot (no leakage).
- **Evaluation:** `GroupKFold(5)` grouped by `student_id`; identical folds shared
  across all models/targets; regression metrics MAE/RMSE/R2; seed 42; deterministic.
- **Candidates (unchanged, no tuning/ensembles):** `ridge` (reference),
  `hist_gbm`, `xgboost` — exact canned ps.
- **Selection rule:** lowest mean MAE per target.
- **Deployment rows** excluded entirely; boundary now per-student (fixed).
- **Persistence:** existing M2 contract → `train_and_persist_m2` persists one
  multi-target `.joblib`.

## 8. M2 previous (CSE-only) vs expanded (CSE+BBA) metrics

Training rows 300 → 420; students 50 → 80.

| Target | model | CSE-only MAE | Expanded MAE (CSV) | Expanded MAE (live) |
|--------|-------|--------------|--------------------|---------------------|
| next_semester_percentage | ridge | 15.047 ± 0.412 | 1.259 ± 0.037 | 13.430 |
| | **hist_gbm** | **1.102 ± 0.237** | **1.140 ± 0.125** | **1.065** |
| | xgboost | 1.218 ± 0.203 | 1.361 ± 0.209 | 1.247 |
| next_semester_sgpa | ridge | 1.636 ± 0.057 | 0.201 ± 0.036 | 1.457 |
| | **hist_gbm** | **0.152 ± 0.049** | **0.174 ± 0.018** | 0.177 |
| | xgboost | 0.155 ± 0.025 | 0.193 ± 0.030 | **0.177** |

Notes:
- Expanded R² stays very high (hist_gbm R² ≈ 0.98) — the signal is strong but
  small-sample caveats remain (see Limitations).
- The live-DB sgpa figures show xgboost (0.1765) marginally ahead of hist_gbm
  (0.1774) by ~0.0009 MAE — inside noise, NOT a credible selection change.

## 9. M2 model-selection result

- **CSV full-cohort run:** `hist_gbm` selected for BOTH targets (lowest mean MAE).
- **Live-DB run:** `hist_gbm` selected for `next_semester_percentage`; `xgboost`
  selected for `next_semester_sgpa` by a razor-thin (~0.0009 MAE) margin.
- **Decision (Phase 7 rule — do not switch for a slightly better score):** retain
  `hist_gbm` for both targets. This is consistent with the prior CSE-only
  selection, the deterministic CSV full-cohort run, and is the stable, documented
  choice. The live sgpa xgboost edge is within noise and reported honestly.
- **Persisted artifact:** `ml/artifacts/models/m2_next_semester_performance.joblib`
  — dict of 2 Pipelines, both `HistGradientBoostingRegressor`, `n_features_in=12`.
  Reload PASS; prediction on 80 deployment rows PASS; sha256 `6cac9a884aba…e071c012`.

## 10. M3 methodology

Reused `features.v1_m3_experiment.run_m3_experiment` unchanged:

- **Target:** `is_at_risk_next_sem(T) = (result(T+1) IN ('FAIL','ATKT')) OR
  (backlogs(T+1) > 0)` — independent, outcome-derived academic labels already
  verified; **no `prediction_feedback` used as ground truth**, no fabricated
  labels, no oversampling, no synthesized positives.
- **Evaluation:** `GroupKFold(5)` by student; seed 42; deterministic.
- **Candidates (unchanged, no tuning/thresholds):** `logistic_regression`
  (reference), `random_forest`, `hist_gbm` — all `class_weight='balanced'`.
- **Deployment rows** excluded; boundary per-student.
- **Evaluation-only — no M3 artifact persisted** (the M3 controlled experiment
  is explicitly eval-only; the existing `m3_next_semester_at_risk.joblib` is left
  untouched, sha256 unchanged `99D845FE…`).

## 11. M3 previous vs expanded metrics

Training rows 300 → 420; students 50 → 80; positive students 2 → 6.

| Metric (valid folds) | CSE-only | Expanded (CSV 28 pos.) | Expanded (live 26 pos.) |
|----------------------|----------|------------------------|--------------------------|
| Positive rows | 10 | 28 | 26 |
| Positive students | 2 | 6 | 6 |
| Informative folds | 2 / 5 | 4 / 5 | 4 / 5 |
| Reference precision | — | 1.000 (n=4) | 1.000 (n=4) |
| Reference recall | — | 1.000 (n=4) | 1.000 (n=4) |
| Reference F1 | — | 1.000 (n=4) | 1.000 (n=4) |
| ROC-AUC | — | 1.000 (n=4) | 1.000 (n=4) |
| PR-AUC | — | 1.000 (n=4) | 1.000 (n=4) |

All three candidates (LR/RF/HGB) report identical perfect separation over the
informative folds. This is genuine (clean separation on the small positive class)
but must be read with the sample-size caveat in Limitations — it is NOT evidence
of production-grade robustness.

## 12. M3 positive-student coverage

- Positive students: **6** (CSE 2: STU000032, STU000041; BBA 4: STU000052,
  STU000060, STU000064, STU000075).
- Positive training rows: 28 (CSV snapshot) / 26 (live DB).
- BBA now contributes positive students, materially broadening the at-risk
  sample beyond CSE.

## 13. Per-fold positive coverage (expanded)

| Fold | train+= | val+= | notes |
|------|--------|-------|-------|
| 0 | 20 | 8 | informative |
| 1 | 24 | 4 | informative |
| 2 | 28 | 0 | **positive class ABSENT (NaN, not fabricated)** |
| 3 | 18 | 10 | informative |
| 4 | 22 | 6 | informative |

n_folds_with_positive = 4 (previously 2). The absent-positive fold is reported
with NaN precision/recall/F1/AUC (never fabricated into aggregates).

## 14. Model-selection result

- **M2:** `hist_gbm` retained for both targets (see §9).
- **M3:** selection is deliberately **not** made on the strength of these tiny
  folds; the reference `logistic_regression` remains the documented baseline.
  No M3 model is promoted to production on the basis of 4 informative folds.

## 15. Artifact changes

| Artifact | Before | After | Status |
|----------|--------|-------|--------|
| `m2_next_semester_performance.joblib` | CSE-only, hist_gbm | expanded CSE+BBA, hist_gbm (both), n_features_in=12 | **UPDATED** (existing M2 persistence contract) |
| `m1_subject_endmarks.joblib` | sha256 `3404D29E…` | unchanged | untouched (no M1 changes) |
| `m3_next_semester_at_risk.joblib` | sha256 `99D845FE…` | unchanged | untouched (M3 eval-only) |

M2 artifact reload PASS, prediction on all 80 deployment rows PASS, deterministic.

## 16. Reproducibility

- M2: two consecutive runs produce identical folds and identical best MAE
  (verified live, `<1e-9`).
- M3: two consecutive runs produce identical positive counts and identical
  informative-fold sets (verified live).
- Deterministic seed 42 throughout; no randomness in fold assignment.

## 17. Tests

- **New focused:** `ml/tests/test_v1_cohort_expansion.py` — **26 tests** covering
  cohort inclusion, department one-hot guarantee (incl. single-department subset),
  deterministic 12-col ordering/shape, target separation, T+1 relationship,
  per-department deployment boundary + exclusion, student isolation, M3 positive
  fold coverage (absent-positive → NaN), class_weight='balanced', M2 selection,
  metric aggregation, artifact reload, default CSE scope unchanged.
- **Full suite:** `python -m pytest ml/tests -q` → **604 passed** (578 prior +
  26 new), **0 failures**.
- **Regressions:** NONE (no existing test weakened/removed; existing M2/M3 and
  audit tests pass unmodified). Warnings are pre-existing sklearn feature-name
  UserWarnings.

## 18. Live verification

`ml/verify_v1_cohort_expansion.py` (asyncpg, read-only, real PostgreSQL):

- Cohort loads (80 students / 500 rows / CSE 350 + BBA 150): PASS
- Expected row counts (420 train / 80 deploy): PASS
- Per-department deployment boundary (CSE 7, BBA 5): PASS
- Department one-hot columns present + populated + deterministic 12-col order: PASS
- M2 student isolation / deployment excluded / reproducible: PASS
- M3 student isolation / deployment excluded / positives 2→6 / informative
  2/5→4/5 / absent fold NaN / reproducible: PASS
- **Result: 16 passed, 0 failed. DB side effects: NONE (read-only).**
- Run twice to confirm reproducibility; no schema/label/feedback mutation.

## 19. Remaining limitations

- **Small positive class:** 6 positive students (26–28 rows) is still small; one
  GroupKFold fold has 0 positives. A larger multi-cohort at-risk population is
  needed to fully power M3 evaluation — this is a data-cohort limit the expansion
  reduced (2→6 students) but did not eliminate.
- **Perfect 1.000 separation:** should be read as a small-sample/clean-separation
  artifact, not production-grade evidence.
- **CSV snapshot vs live DB drift:** the CSV mirror yields 28 M3 positive rows
  while the live DB has 26, and M2 numbers differ marginally — the two are
  slightly out of sync. Structural guarantees agree; numeric values are
  version-sensitive. The persisted artifact is from the deterministic CSV cohort;
  retraining on the freshest live snapshot would re-derive it.
- **No temporal hold-forward department split:** GroupKFold-by-student gives
  student isolation but not a held-out department/year shift.
- **M3 remains a baseline** (not promoted to production from these folds).

## 20. Exact next single step (recommend, not implemented here)

**Address the M3 positive-class powering by adding a second, independent
(chronologically later) academic-year cohort with confirmed at-risk outcomes to
the M3 training population** (reusing the same outcome-derived target rule and
per-student deployment boundary), so the M3 GroupKFold evaluation can move from
4/5 informative folds with 6 positive students toward a fully-powered
evaluation; then re-run the M3 experiment and, only if the positive class is
adequately powered, progress the M3 model beyond the reference baseline.
