# M1 / M2 / M3 — OLD (V1) vs NEW (V2) Model Comparison and Recommendation

**Status:** COMPARISON COMPLETE — RECOMMENDATION ISSUED — CONTENT ONLY (no legacy code/model/Supabase modified, deleted, or retrained)
**Date:** 2026-09-01
**Companion docs:** `existing_ml_audit.md`, `ml_v2_architecture.md`, per-model V2 validation reports (see §8).

**Mandate enforced (safety):**
- ✅ Nothing deleted, renamed, or modified. No legacy model, artifact, or code changed.
- ✅ No Supabase modification (read-only only).
- ✅ No retraining performed to improve numbers.
- ✅ All OLD + V2 artifacts were **loaded read-only** to confirm loadability and inspect contents.
- ✅ Output is limited to this comparison + `.json` + the final recommendation. Legacy retirement/cleanup is a **separate later task** and is deliberately **not** executed here.

---

## 0. Executive Summary — Winner per model

| Model | OLD (V1) | NEW (V2) | **WINNER** | Confidence | Headline reason |
|---|---|---|---|---|---|
| **M1** Subject end-marks | `hist_gbm` (12 feat) | `ridge` (39 feat) | **V2** | **High** | V1 trained on synthetic/stationary data (metrics untrustworthy); V2 is the only real-data, leak-checked, baseline-corrected estimator |
| **M2** Next-semester SGPA/% | `hist_gbm` per-target | `random_forest`(sgpa) / `ridge`(pct) | **V2** | **High** | V1's R²≈0.99 is a proven autocorrelation artifact; V2 verified against carry-forward baseline on a held-out transition |
| **M3** At-risk | `logistic_regression` Pipeline | `random_forest` (35 feat) | **V2** | **Medium** | V1 is invalid (6 positive students, gate FAIL, BLOCKED in prod); V2 is the only honest classifier but is *provisional* — 28 positives, same-cohort holdout → **NEEDS FURTHER VALIDATION** |

> **Never decide "newer is better."** These verdicts rest on evidence quality, leakage safety, generalization, prediction usefulness, reliability, and the project's validation contract — not on chronology.

---

## 1. Validation-protocol compatibility (rule #: never compare incompatible protocols as equivalent)

A direct numeric comparison of OLD vs V2 headline metrics is **invalid** because they were produced under different contracts:

| Dimension | OLD (V1) | NEW (V2) | Comparable? |
|---|---|---|---|
| Data type | **Academically synthetic**, deterministic seed (80 students, 500/3293 rows) | **Real** CSE_6A_1200 cohort (1,200 students, 58,800–68,400 rows) | ❌ No — different data quality regime |
| Target | Same semantic target | Same semantic target | ✅ Yes (per model) |
| Validation | GroupKFold(5) by student + temporal multi-holdout | GroupKFold(5)×3-seed **+ temporal hold-forward** | Partial — V2 adds a genuinely held-out future window |
| Cohort coverage | 1 synthetic cohort | 1 real cohort (single division) | Partial |
| Baseline-corrected skill | None | Mean + prior-semester / carry-forward baselines | ✅ Only V2 expresses lift-over-baseline |

**Consequence:** OLD headline numbers (M1 MAE 3.18, M2 R² 0.997, M3 F1 0.80) **must not be quoted** as OLD outperforming V2. The lower MAE / near-perfect R² of V1 are artifacts of a near-stationary deterministic generator (feature–target correlations 0.86–0.99, §5), not genuine skill. V2's higher MAE vs V1 is expected evidence of moving from synthetic to real data, **not** a regression.

---

## 2. Phase C — M1 OLD vs V2 (subject end-marks regression)

### Contract
- **Target:** `end_sem_marks` [0,70].
- **Prediction point (both):** during semester T, after internal/mid/attendance recorded, before end-exam.
- OLD prediction point uses semester-level attendance; V2 adds weekly attendance, learning activity, lifestyle, prior history.

### Evidence

| Item | OLD (V1) `m1_subject_endmarks` | V2 `m1_v2_subject_endmarks` | Valid? |
|---|---|---|---|
| Base | `ml/src/m1/`, artifact 441 KB | `ml/v2/m1_subject_prediction/`, artifact 6.9 KB | — |
| Algorithm | `HistGradientBoostingRegressor` | `ridge` | — |
| Features | 12 encoded | 39 | V2 richer |
| Cohort / rows | 80 students, 3,293 labeled / 557 deploy (synthetic) | 1,200 students, 58,800 train / 8,400 temporal holdout / 67,200 final (real) | **V2 real** |
| CV MAE | 3.18±0.11 | 6.319±0.040 | V1 NOT trustworthy |
| CV R² | 0.82 | 0.434 | V1 NOT trustworthy |
| Temporal MAE | ~3.23 | 6.302 | V1 NOT trustworthy |
| Temporal R² | — | 0.423 | — |
| Lift vs mean baseline | — | **25%** (8.413 → 6.302) | ✅ |
| Lift vs prior-sem mean baseline | — | **16%** (7.509 → 6.302) | ✅ |
| Leakage | No forbidden columns; synthetic caveat | PASS (no forbidden features found) | ✅ |
| Train-val gap (temporal) | — | +0.012 (essentially none) | ✅ |

### Verdict
**V2 wins (High confidence).** V1's metrics are a property of synthetic, near-stationary data (internals correlate r≈0.81–0.87 with the target, so the model interpolates a deterministic generator). V2 is the only M1 that (a) trains on real data, (b) demonstrates genuine lift over declared baselines on a held-out semester, (c) passes leakage checks, and (d) shows a near-zero train/validation gap. OLD M1 → **REBUILDED** ⇒ keep OLD artifact **ARCHIVE**, promote V2.

---

## 3. Phase D — M2 OLD vs V2 (next-semester performance)

### Contract
- **Targets:** `next_semester_percentage`, `next_semester_sgpa`.
- Both use a per-student T→T+1 shift; V2 excludes the degenerate internship transition T=7→8.

### Evidence

| Item | OLD (V1) `m2_next_semester_performance` | V2 `m2_v2_next_semester` | Valid? |
|---|---|---|---|
| Base | `ml/src/m2/` + `v1_m2_regression.py`, artifact 570 KB | `ml/v2/m2_next_semester_prediction/`, artifact 7.7 MB | — |
| Algorithm | `HistGradientBoostingRegressor` per target | sgpa=`random_forest`, pct=`ridge` | — |
| Features | 11 raw → 12 encoded | 34 | V2 richer |
| Cohort / rows | 80–300/420 labeled (synthetic) | 1,200 students, 6,000 train / 1,200 holdout (real) | **V2 real** |
| CV MAE (sgpa/%) | 0.152 / 1.102 | 0.1932 / 2.4898 | V1 NOT trustworthy |
| CV R² (sgpa/%) | 0.991 / 0.997 | 0.700 / 0.816 | V1 NOT trustworthy |
| Temporal R² (sgpa/%) | — | 0.591 / 0.737 | ✅ |
| Temporal MAE (sgpa/%) | — | 0.2235 / 2.9745 | ✅ |
| **Lift vs carry-forward (sgpa/%)** | — | **18.6% / 15.3%** | ✅ |
| Leakage | No target leakage; **autocorrelation red flag confirmed** | PASS (T+1 outcome columns forbidden) | ✅ |
| Train-val gap | — | -0.060 / -0.496 (moderate) | ⚠️ noted |

### Verdict
**V2 wins (High confidence).** The legacy audit independently verified V1's near-perfect R² (0.997 %) is an **autocorrelation artifact**: `semester_percentage` correlates 0.9919 with next-% and `semester_sgpa` 0.9749 with next-SGPA; mean per-student change between semesters is tiny (≈1.31 pct / ≈0.20 SGPA), so the generator lets the model "predict the future" from the present. V2 neutralizes this by (a) comparing against the strong carry-forward baseline and (b) proving real lift on a held-out transition. OLD M2 → **REBUILDED** ⇒ keep OLD artifact **ARCHIVE**, promote V2. Note: V2 has a moderate train-val gap on the percentage target (ridge) — monitor, but discrete lift over carry-forward is the decisive evidence.

---

## 4. Phase E — M3 OLD vs V2 (at-risk classification)

### Contract
- **Target:** `is_at_risk_next_sem` = 1 if T+1 result FAIL/ATKT **or** T+1 backlog_count>0.

### Evidence

| Item | OLD (V1) `m3_next_semester_at_risk` | V2 `m3_v2_at_risk` | Valid? |
|---|---|---|---|
| Base | `ml/src/features/v1_*m3*` + `retrain_m3.py`, artifact 2 KB | `ml/v2/m3_at_risk_prediction/`, artifact 1.7 MB | — |
| Algorithm | `logistic_regression` Pipeline (balanced) | `random_forest` | — |
| Features | 11 raw → 12 encoded | **35** | V2 richer |
| Cohort / positives | 420 rows: 392 neg / **28 pos from 6 students** (synthetic) | 7,200 rows train; holdout **28 pos / 1,172 neg** (real) | **V2 real** |
| Reported metric quality | F1 0.80 / ROC-AUC 1.00 — **invalid** (gate FAIL; small sample) | Holdout **recall 0.571**, PR-AUC 0.282 | V1 invalid |
| Threshold | default 0.5 | tuned **0.64** (+ threshold_metrics saved) | V2 disciplined |
| Beat baseline | No baseline declared | Base-rate PR-AUC 0.023; baseline recall **0.000 / 0.000**; V2 recall 0.571 | ✅ |
| Leakage | Main path guarded; **`retrain_m3.py` diverges** (StratifiedKFold, non-canonical label, schema alias) | PASS (leakage_check) | V2 clean |
| Production status | **BLOCKED** (gate FAIL; never served) | Live, but all 1,200 students at semester 8 → **NO_DATA** honest boundary | V2 honest |

### Verdict
**V2 wins (Medium confidence) — and is flagged NEEDS FURTHER VALIDATION.**
- OLD M3 is **invalid**: only 6 unique positive students (28 rows) make every metric a small-sample artifact, the statistical validation gate returns **FAIL**, and inference is correctly **BLOCKED**. `retrain_m3.py` additionally carries a leakage/methodology divergence (StratifiedKFold, `sgpa<4.0` non-canonical label, `department_code` schema alias) and is **unsafe to reuse**.
- V2 is the **only load-bearing** M3: real data, 35 features, tuned threshold, holdout recall 0.571 vs a baseline recall of 0.000 and PR-AUC 0.282 vs base-rate 0.023, leakage PASS.
- **Caveats that cap confidence at Medium:** holdout has only **28 positives**; the temporal holdout is the **same cohort one semester later** (no fully unseen cohort); the live cohort is already at semester 8, so the endpoint currently returns NO_DATA (an honest deployment boundary, not a defect). Per the architecture contract, M3 remains provisional until a genuinely unseen cohort with sufficient real positives is available.

OLD M3 → **REBUILDED (provisionally)** ⇒ keep OLD artifact **ARCHIVE**; promote V2 with a standing **NEEDS FURTHER VALIDATION** marker on the positive class.

---

## 5. Common-state risk that made V1 numbers untrustworthy (applies to all three)

The legacy audit established, across M1/M2/M3, that reported metrics were inflated by:

1. **Synthetic near-stationary data.** Consequences-grade features (`semester_percentage`, `semester_sgpa`, `internal_marks`, `mid_sem_marks`, `attendance`) correlate **0.86–0.99** with their own next-period/final targets.
2. **Tiny statistical sample.** M1/M2 rely on ~80 students; M3's positive class is 6 students / 28 rows. Model selection and "gains" between similar algorithms were not statistically significant.

None of these are present in V2's real-data validation, which is why V2's (numerically "worse" for M1/M2) metrics are the ones that constitute evidence.

---

## 6. Phase F–N — cross-cutting checks

### 6.1 Prediction sanity (Phase G — read-only artifact load) — PASS
All six artifacts loaded read-only with `joblib.load`:

| Artifact | Type | Features | Load |
|---|---|---|---|
| M1 OLD `m1_subject_endmarks.joblib` | `HistGradientBoostingRegressor` | 12 | ✅ |
| M2 OLD `m2_next_semester_performance.joblib` | 2× `Pipeline` (pct, sgpa) | 11→12 | ✅ |
| M3 OLD `m3_next_semester_at_risk.joblib` | `Pipeline` | 12 | ✅ |
| M1 V2 `m1_v2_subject_endmarks.joblib` | `Ridge` + `M1Preprocessor` | 39 | ✅ |
| M2 V2 `m2_v2_next_semester.joblib` | per-target `random_forest`/`ridge` + `M2Preprocessor` | 34 | ✅ |
| M3 V2 `m3_v2_at_risk.joblib` | `RandomForestClassifier` + `M3Preprocessor` | 35 | ✅ |

### 6.2 Leakage audit — V2 PASS (all three); OLD mostly-OK but synthetic / one unsafe path
- M1 OLD: no forbidden columns; metrics untrustworthy. M1 V2: PASS.
- M2 OLD: no target leakage but autocorrelation artifact. M2 V2: PASS, T+1 outcome columns forbidden.
- M3 OLD: main path guarded **but** `retrain_m3.py` unsafe (see §4). M3 V2: PASS.

### 6.3 Fairness / demographic categories
- Both generations use only `gender` (deprecated-binary) and `department_name` as protected attributes; V2 adds no sensitive identity attribute beyond these.
- **Available evidence is insufficient for a formal fairness metric** (single cohort, single division). We do **not** claim parity. V2 retains the same protected attributes as input but reports no parity breakdown → flagged for future bias audits. No blocking issue identified in this protocol.

### 6.4 Production suitability (12 criteria) — V2

| # | Criterion | M1 V2 | M2 V2 | M3 V2 |
|---|---|---|---|---|
| 1 | Trained on real data | ✅ | ✅ | ✅ |
| 2 | Leakage-free validation | ✅ | ✅ | ✅ |
| 3 | Temporal hold-forward | ✅ | ✅ | ✅ |
| 4 | Lift over declared baseline | ✅ | ✅ | ✅ |
| 5 | Statistical sufficiency | ✅ | ✅ | ⚠️ 28 pos (provisional) |
| 6 | Tuned decisicion threshold | — | — | ✅ 0.64 |
| 7 | Reload test | PASS | PASS | PASS |
| 8 | Prediction test | PASS | PASS | PASS |
| 9 | Backend API + tests | ✅ | ✅ | ✅ (34 tests) |
| 10 | Frontend contract | ✅ | ✅ | ✅ |
| 11 | Full regression passed | ML 841 | ML 841 | ML 841; backend + frontend green |
| 12 | Typecheck | ✅ | ✅ | ✅ |

> M3 V2 fails **production terminal** only on criterion 5 (positive-class sample); it is deployed with an explicit **NO_DATA** boundary for the current cohort and must be re-gated once a genuinely unseen cohort with enough real positives is available.

### 6.5 Recommended retirement classifications (for the *separate* later cleanup task — NOT executed here)

| Asset | Recommendation |
|---|---|
| OLD M1 `ml/artifacts/models/m1_subject_endmarks.joblib` + `ml/src/m1/{config,data,evaluate,multi_holdout,readiness,temporal,train_m1}.py` | **ARCHIVE** (keep leakage/temporal-validation methodology as reference; artifact metrics obsolete) |
| OLD M2 `ml/artifacts/models/m2_next_semester_performance.joblib` + `ml/src/m2/*` + `ml/src/features/v1_m2_regression.py` | **ARCHIVE** (artifact R²≈0.997 invalid; pipeline reusable) |
| OLD M3 `ml/artifacts/models/m3_next_semester_at_risk.joblib` + `ml/src/features/v1_*m3*` | **ARCHIVE** (invalid; gate/label-builder methodology value kept) |
| **`ml/src/retrain_m3.py`** | **BLOCKED FROM REUSE** until StratifiedKFold / non-canonical label / schema-alias divergences are fixed |
| OLD M1/M2/M3 reports (`m1_report.md`, `m2_report.md`, `m3_report.md`, `m1_verification.md`) | **ARCHIVE** — do not quote headline metric numbers as evidence |
| V2 M1/M2/M3 artifacts + reports + backend + frontend | **KEEP / PROMOTE** (M3 with an explicit further-validation marker) |

### 6.6 Regression / Supabase safety
- Full regression (Phase T, prior): **ML suite 841 passed**; backend 1442 passed (excluding pre-existing untracked Python 3.12 `asyncio` ordering issue in `test_analytics*`, unrelated to this comparison); frontend 150/150; typecheck PASS.
- **No pre-existing test was changed/removed; no legacy model or Supabase object was touched during this comparison.**

---

## 7. Final Recommendation Report

1. **M1 — Subject end-marks: WINNER = M1 V2** (`ridge`, 39 features). Confidence: **High**. OLD M1 is a synthetic-data artifact; V2 is the only real-data, baseline-corrected, leak-checked estimator (25% / 16% lift on held-out semester 7).
2. **M2 — Next-semester performance: WINNER = M2 V2** (`random_forest` sgpa, `ridge` pct). Confidence: **High**. OLD M2's R²≈0.99 is a proven autocorrelation artifact; V2 proves real skill with 18.6% / 15.3% lift over carry-forward on a held-out transition.
3. **M3 — At-risk: WINNER = M3 V2** (`random_forest`, 35 features, threshold 0.64). Confidence: **Medium**, and **flagged NEEDS FURTHER VALIDATION**. OLD M3 is statistically invalid (6 positive students, gate FAIL, BLOCKED). V2 is the only load-bearing classifier (holdout recall 0.571 vs baseline 0.000; PR-AUC 0.282 vs base-rate 0.023) but remains provisional until a genuinely unseen cohort supplies sufficient real positives.

**Recommended dispositions (executed in the separate cleanup task):**
- **ARCHIVE** all three OLD artifacts + their reports (do not quote their headline numbers).
- **BLOCK** `retrain_m3.py` reuse until divergence-free.
- **KEEP/PROMOTE** M1 V2, M2 V2; promote M3 V2 with the further-validation marker.
- **No OLD model is deleted or modified here; no Supabase change; no retraining.**

---

## 8. Sources

- `plan_1200_6a/existing_ml_audit.md` (legacy classification: M1/M2/M3 REBUILD; M4 keep; `retrain_m3.py` blocked)
- `plan_1200_6a/ml_v2_architecture.md` (v2 design, baseline-lift and M3 promotion-gate rules)
- `ml/reports/m1_report.md`, `m1_verification.md`, `m2_report.md`, `m3_report.md` (legacy headline metrics — cited only to disqualify)
- `ml/v2/m1_subject_prediction/reports/m1_v2_validation_report.md`
- `ml/v2/m2_next_semester_prediction/reports/m2_v2_validation_report.md`
- `ml/v2/m3_at_risk_prediction/reports/m3_v2_validation_report.md`
- Read-only artifact inspection (§6.1) of all six `.joblib` files