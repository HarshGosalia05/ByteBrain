# Integrated M1/M2/M3 ML Readiness / Consistency Audit

**Step:** Integrated M1/M2/M3 ML Readiness / Consistency Audit (post-M1/M2/M3 implementation)
**Scope guard:** Audit only. No M4, deployment, prediction API, dashboard integration, GenAI, auth, ETL, DB/schema changes, dataset expansion, new training, tuning, or production deployment.

---

## 1. Objective

Determine whether the completed M1/M2/M3 ML layers are internally consistent and
ready to proceed to the next ML/product step, by verifying, in a single integrated
view, the cross-model invariants that per-model tests do not cover simultaneously:

1. Cross-model **target separation** (no model's target leaks into another model's features).
2. **Temporal consistency** (M2/M3 T+1 horizon; deployment = last semester / target NULL; M1 pre-end-semester signals).
3. **Grain / student isolation** (each model's grain is unique; student id preserved and aligned to features).
4. **Feature-contract consistency** (12 encoded columns; M2/M3 identical feature order; matches `features.py` contract).
5. **Forbidden-feature protection** across all models, including the V1 union guard.
6. **Artifact integrity** (existence, loadability, correct type, feature count, determinism, unchanged hashes).
7. **Evaluation consistency / reproducibility** (GroupKFold(5) by student upheld; repeated audit identical).
8. **Dataset limitations** (current, not expanded) — labeled technically verified versus statistically limited.

The audit is **read-only**: no DB writes, no ETL, no artifact writes/no retraining, no model selection changes.

---

## 2. Contracts (Source of Truth)

| Model | Grain | Target(s) | Raw → Encoded | Selected Model | Artifact path |
|-------|-------|-----------|---------------|----------------|---------------|
| **M1** | `(student_id, subject_id, semester_no)` | `end_sem_marks` (0–70, NULL=deploy) | 8 → 12 | `hist_gbm` | `ml/artifacts/models/m1_subject_endmarks.joblib` |
| **M2** | `(student_id, semester_no)` | `next_semester_percentage` + `next_semester_sgpa` (T+1 via `shift(-1)`) | 11 → 12 | `hist_gbm` (both) | `ml/artifacts/models/m2_next_semester_performance.joblib` |
| **M3** | `(student_id, semester_no)` | `is_at_risk_next_sem` (binary) | 11 → 12 | `logistic_regression` (baseline/reference; not production-selected beyond this) | `ml/artifacts/models/m3_next_semester_at_risk.joblib` |

- **M1 config:** `ml/src/m1/config.py` (MODEL_ALGORITHMS → hist_gbm, RANDOM_STATE=42).
- **M2 config:** `ml/src/m2/config.py` (MODEL_ALGORITHMS → hist_gbm both targets, RANDOM_STATE=42).
- **M3 config:** `ml/src/m3/config.py` (MODEL_ALGORITHMS → LogisticRegression baseline, RANDOM_STATE=42).
- **Evaluation:** all three use GroupKFold(5) grouped by student (`m1/evaluate.py`, `m2/evaluate.py`, `m3/evaluate.py`).
- All use `SimpleImputer` (+ optional scaler for M3) with `n_features_in = 12`.

---

## 3. Target Definitions & Cross-Model Separation

Registry: `ml/src/feature_config.py` (TARGETS and forbidden lists), `ml/src/features.py` (M1/M2/M3_CONTRACT).

- M1 target `end_sem_marks` is **not** present in M2/M3 raw features or encoded matrices.
- M2 targets `next_semester_percentage`/`next_semester_sgpa` are **not** present in M1 or M3 features.
- M3 target `is_at_risk_next_sem` is **not** present in M1 or M2 features.
- M2's forbidden list contains `is_at_risk_next_sem`; M3's contains both M2 targets.
- All three target sets are pairwise disjoint.
- No target name (or target-source column) appears as a feature of any model.

**Verified:** at the contract level AND at the actual encoded-DataFrame level.

---

## 4. Feature Contracts

- All three models consume **12 encoded columns**.
- M2 (`m2/data.py.one_hot_encode`) and M3 (`m3/data.py.one_hot_encode`) produce **byte-identical 12-column order**:
  `…, department_name_BBA, department_name_CSE, is_male`, matching `features.py` `expected_cols`.
- M1 uses its own 12-col encoding (8 raw → 12 encoded) with `hist_gbm`; preprocess is `[]`.
- `get_encoded_feature_names()` is **not** authoritative for M2/M3 ordering (produces `_dummy_` columns) — ordering is verified directly from the encoded matrices.

---

## 5. Temporal Boundaries (Leakage Prevention)

- **M1:** target `end_sem_marks` is scored at the end of the semester; the feature matrix uses only **pre-end-semester** signals (internal_marks, mid_sem_marks, attendance, credits, semester_no, subject_type, department, is_male). M1's forbidden list excludes grade/total_marks etc. `m1_pre_end_signals = True`.
- **M1 deployment** rows = those with `end_sem_marks` NULL (no ground truth), i.e., the unlabeled future semester.
- **M2/M3:** target is `shift(-1)` per student → strictly **T+1** future. Verified from the `summary` table: every training row's next-semester target is a strictly larger semester than the feature semester (`m2_tgt_strictly_future = True`).
- **Deployment rows** = last semester per student (target NULL) — they can never serve as evaluation ground truth (`deploy_is_last_semester = True`).

---

## 6. Grain / Student Isolation

- M1 grain `(student_id, subject_id, semester_no)` — unique, no duplicate (verified live: 0 dup across 3,850 rows).
- M2 grain `(student_id, semester_no)` — unique across 500 rows.
- M3 grain `(student_id, semester_no)` — unique across 500 rows.
- `student_id` is preserved and aligned with each encoded feature matrix (no row misalignment).
- GroupKFold(5) by student is upheld (no student appears in both train and val fold).

---

## 7. Artifact Integrity (read-only)

| Artifact | loads | type (expected) | n_features | deterministic | in-range | unchanged |
|----------|-------|-----------------|-----------|---------------|----------|-----------|
| `m1_subject_endmarks.joblib` | yes | `HistGradientBoostingRegressor` | 12 | yes | yes (clipped [0,70]) | yes |
| `m2_next_semester_performance.joblib` | yes | `HistGradientBoostingRegressor` | 12 | yes | n/a (no clip contract; finite) | yes |
| `m3_next_semester_at_risk.joblib` | yes | `LogisticRegression` | 12 | yes | yes (binary {0,1}) | yes |

- M1 hash `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E` matches the documented value; mtime 12-Aug-2026 unchanged.
- M2/M3 hashes stable across this session; **no persistence side effects** produced by the audit.

---

## 8. Evaluation Consistency & Reproducibility

- Both regression (M2) and classification (M3) use GroupKFold(5) by student; absent-positive folds in M3 are handled without fabricating metrics.
- The integrated audit is deterministic: two consecutive runs produce identical results (`reproducibility = True`).
- Feature engineering verification (M1/M2/M3/M4) against the live PostgreSQL database is stable across runs.

---

## 9. Dataset Limitations (current, not expanded)

| Model | students | labeled rows | deployment rows | grain | notes |
|-------|----------|--------------|-----------------|-------|-------|
| M1 | 80 | 3,293 | 557 | student/subject/semester | end_sem_marks 0–70 |
| M2 | 80 | 420 | 80 | student/semester | T+1 targets |
| M3 | 80 | 420 | 80 | student/semester | **positive class = 28** (underpowered) |

Live DB confirms: M1 3,850 rows (3,291 train / 559 deploy), M2/M3 500 rows (420 train / 80 deploy), M2 target mean 63.97, M3 positive rate 0.062.

---

## 10. Cross-Model Findings & Issues

### Verified (technically sound)
1. All cross-model target-separation invariants hold (no leakage).
2. Temporal T+1 horizon is strictly future; deployment rows carry no ground truth.
3. Grains unique and isolated; GroupKFold by student upheld.
4. Feature orders identical across M2/M3 and match the M1/M2/M3 contracts (12 cols).
5. Forbidden-feature protection holds for all models, including the V1 union guard.
6. Artifacts load, are the correct type, deterministic, in range, and unchanged.
7. Integrated audit + 27 focused tests + full suite pass with **no regressions**.

### Documented concerns (not blocking consistency; require attention before PRODUCTION)
1. **M2 artifact trained on CSE-only data** (V1 `train_and_persist_m2`, mtime 28-Aug) while the M2 feature contract exposes `department_name_BBA`/`department_name_CSE`. The artifact still satisfies `n_features_in = 12` and the column order (so inference is contract-safe), but the training population is CSE-concentrated — BBA generalization is unverified on real BBA data. This is a **statistical limitation**, not a contract break.
2. **M3 positive class underpowered** (28 positives / 420 rows) — the M3 selected model is a documented **baseline/reference** (class-weighted LogisticRegression) and is explicitly **not** claimed production-ready for the at-risk flag without more positives.
3. **Data volume small (80 students)** — all models are technically verified but statistically limited; results are directional, not population-general.

---

## 11. Verifiable Evidence

- `ml/tests/test_v1_ml_readiness_audit.py` — 27 new focused cross-model tests (PASS).
- `python -m pytest ml/tests -q` → **578 passed** (baseline 551 + 27 new), **0 failures**.
- Live verification `verify_feature_engineering.py` (asyncpg, read-only, PostgreSQL) → **24/24 passed**.
- Audit module: `ml/src/features/v1_ml_readiness_audit.py` (CSV data layers; tests run without DB).
- M1 hash unchanged: `3404D29E…C6431E`, mtime 12-Aug-2026.

---

## 12. What Was NOT Changed

- No model selection changed (M1 `hist_gbm`, M2 `hist_gbm`, M3 baseline LR retained).
- No artifacts rewritten/retrained; hashes unchanged.
- No DB/schema changes; no ETL.
- No existing tests weakened or deleted; no tests altered to hide failures.
- No M4, deployment, prediction API, dashboard, GenAI, auth, dataset expansion, tuning, or production integration.

---

## 13. Distinction: Technically Verified vs Statistically Limited vs Production-Ready

- **Technically verified (this audit):** contracts, leakage controls, temporal boundaries, grain isolation, feature ordering, artifact integrity, reproducibility.
- **Statistically limited:** small cohort (80 students), CSE-concentrated M2 artifact, M3 low positive class.
- **Not claimed production-ready:** M3 (baseline only) and M2's cross-department generalization require more data before any production gate.
