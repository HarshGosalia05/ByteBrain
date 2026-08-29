# Unified OFFLINE Inference Contract (M1/M2/M3)

## 1. Objective

Build a single, centralized, **OFFLINE-only** inference contract/layer for the
existing M1, M2, and M3 models: a safe, reusable, deterministic prediction
boundary that reuses the existing feature preparation, model registry/loading,
artifact contracts, and readiness/validation information.

This step is **NOT** an API, dashboard, deployment, GenAI, model training, or
model promotion. No M3 promotion occurred. M3 remains BLOCKED.

## 2. Existing architecture reused (Phase 1)

The contract is a thin, centralized adapter over the authoritative existing
layers — no parallel feature-engineering or model-loading architecture was
created:

| Concern | Reused module |
|---|---|
| Model / artifact loading | `ml/src/registry.py` → `registry.load_model()` (cached, shape-validated) |
| Feature preparation (exact training-time encoding/order/preprocessing) | `ml/src/features.py` → `prepare_m1/m2/m3_inference` (re-exported by `features` package) |
| M1 prediction clipping `[0,70]` | `ml/src/m1/config.py` → `TARGET_MIN=0.0`, `TARGET_MAX=70.0` |
| M1 readiness semantics | `ml/src/m1/readiness.py` (technically-ready-for-offline-scoring) |
| Forbidden/leakage features | `ml/src/feature_config.py` → `ALL_FORBIDDEN` |
| M3 validation-blocked state | `ml/src/features/v1_m3_validation_gate.py` (verdict FAIL) |
| M3 reference model identity | `ml/src/features/v1_m3_experiment.py` → `REFERENCE_MODEL="logistic_regression"` |
| Model identity / metadata | Artifact `metadata` (M1: version 1, `hist_gbm`, 12 features) |

## 3. Inference contract

`ml/src/features/v1_inference_contract.py`. Single unified dispatcher
`predict(model_id, row, ...)` plus per-model entry points. Every call runs:

1. Input validation (missing fields, types, finite numerics, categorical values,
   semester range, forbidden/target leakage rejection).
2. Feature-contract enforcement (exact 12-feature set, exact order, BBA/CSE
   one-hot presence).
3. Model load through the authoritative registry.
4. Prediction via the existing feature-prep + artifact path.
5. Postprocessing (M1 clipping `[0,70]`, 1-decimal rounding; M2 per-target
   rounding; M3 gated).
6. Deterministic structured `InferenceResult`.

`InferenceResult` exposes: `model_id`, `readiness_status`, `prediction_available`,
`prediction`, `target`, `student_id`, `subject_id` (M1), `semester_no`,
`feature_count`, `feature_contract`, `model_algorithm`, `artifact_hash`, `reason`,
`validation_ok`. No sklearn objects are serialized; `to_dict()` returns plain data.

## 4. Model readiness states

`READY`, `BLOCKED`, `UNAVAILABLE`, `INVALID_INPUT`, `ERROR`.

- **M1 → READY** (passed temporal multi-holdout validation + prediction-readiness).
- **M2 → READY** (CSE+BBA cohort expansion completed; artifact authoritative).
- **M3 → BLOCKED** (positive-class statistically underpowered; validation gate FAIL).

M3 is never `READY`. The standardized reason returned is:

> "M3 validation gate is blocked due to insufficient positive-class statistical
> coverage ... No production prediction is available."

## 5. M1 contract

- Grain `(student_id, subject_id, semester_no)`; target `end_sem_marks`.
- Input fields: `student_id, subject_id, semester_no, internal_marks,
  mid_sem_marks, attendance_percentage, credits, subject_type, department_name,
  gender`.
- Model: `hist_gbm` (`HistGradientBoostingRegressor`), version 1, 12 features.
- Output: single `float`, **clipped to `[0,70]`**, rounded to 1 decimal.
- `prediction_available=True`.

## 6. M2 contract

- Grain `(student_id, semester_no)`; targets `next_semester_percentage`,
  `next_semester_sgpa` (T+1).
- Input fields: `student_id, semester_no, subjects_registered,
  credits_registered, credits_earned, semester_total_marks, semester_percentage,
  semester_sgpa, semester_attendance_percentage, backlog_count, department_name,
  gender`.
- Model: `hist_gbm` pipelines, one per target; 12 features.
- Output: dict `{"next_semester_percentage": float(2dp),
  "next_semester_sgpa": float(2dp)}`.
- `prediction_available=True`.

## 7. M3 blocked behavior

- Grain `(student_id, semester_no)`; target `is_at_risk_next_sem` (T+1).
- Reference model identity `logistic_regression` (persisted artifact is a
  Pipeline); readiness **BLOCKED**.
- Normal inference returns `readiness=BLOCKED`, `prediction_available=False`,
  `prediction=None`, and the standardized blocked reason.
- An **explicit** `allow_offline_score=True` opt-in computes the raw model output
  for internal/validation purposes only, but still reports `BLOCKED` and
  `prediction_available=False`; it never surfaces a production-facing prediction.
- The M3 validation gate is **not** bypassed.

## 8. Feature contract

Authoritative **exact 12 encoded columns, exact order**:

- M1: `internal_marks, mid_sem_marks, attendance_percentage, credits,
  semester_no, subject_type_Internship, subject_type_Laboratory,
  subject_type_Project, subject_type_Theory, department_name_BBA,
  department_name_CSE, is_male`.
- M2/M3: `semester_no, subjects_registered, credits_registered, credits_earned,
  semester_total_marks, semester_percentage, semester_sgpa,
  semester_attendance_percentage, backlog_count, department_name_BBA,
  department_name_CSE, is_male`.

Both include `department_name_BBA` and `department_name_CSE` one-hot columns.
The contract enforces length, names, and order; a mismatch refuses inference
(no silent reorder/drop/injection). Encoding/preprocessing come only from the
authoritative prep + persisted pipeline — no preprocessing is fitted at
inference time.

## 9. Leakage controls

The contract rejects any input carrying target/forbidden/future/feedback
columns (Phase 9). Reused `feature_config.ALL_FORBIDDEN` plus explicit targets
and feedback columns. It rejects e.g.:

- `end_sem_marks` (M1 target)
- `next_semester_percentage`, `next_semester_sgpa` (M2 targets)
- `is_at_risk_next_sem`, `semester_result`, future-outcome fields (M3/M2)
- `prediction_feedback`, `prediction`
- M1 subject-level future/labeled columns (`latest_sgpa`, `overall_cgpa`, etc.)

Inference never generates labels; it consumes features and returns model outputs
only.

## 10. Model-loading behavior

All models are loaded via `registry.load_model(model_id)` (authoritative,
cached, shape-validated). The loaded object is used read-only. Artifact identity
(SHA-256) is captured and returned in every result. No artifact is written or
regenerated.

## 11. Prediction postprocessing

- **M1**: `np.clip(raw, 0, 70)` then `round(..., 1)`. Reuses `m1/config.py`.
- **M2**: per-target pipelines produce `next_semester_percentage` and
  `next_semester_sgpa`, rounded to 2 decimals (existing contract, no invented
  thresholds).
- **M3**: no normal prediction while BLOCKED.

## 12. Deterministic behavior

Identical input → identical `InferenceResult` (verified for M1, M2, and the M3
blocked path, each run multiple times). Determinism compared structurally via
the established rounding of already-rounded contract values (no exact-string
floating-point comparison).

## 13. Tests

New file `ml/tests/test_v1_inference_contract.py` (focused suite, 42 tests)
covering all required points 1–25:
supported ids, M1/M2 READY, M3 BLOCKED, prediction shapes/types, M1 clipping,
M2 output contract, M3 blocked response, missing/invalid/non-finite/categorical
input, target+forbidden leakage, exact 12-feature + exact-order + BBA/CSE
contract, registry loading, artifact identity, determinism (M1/M2/M3), no DB
writes, no artifact writes.

- Focused: `42 passed`.
- Relevant M1/M2/M3/features/inference/registry subset: `198 passed`.
- Full `ml/tests` suite: **713 passed, 0 failed, 246 warnings** (prior baseline
  671; +42 new). No existing tests weakened or deleted.

## 14. Live verification

`ml/verify_v1_inference_contract.py` (read-only, real existing CSV data +
authoritative artifacts): **33 passed, 0 failed**. Verified M1 load+score,
M2 load+score, M3 remains BLOCKED, 12-feature/order/BBA-CSE contracts, finite
outputs, M1 `[0,70]`, determinism (repeated runs), artifacts unchanged, and no
DB/artifact write code.

## 15. Artifact hashes

Byte-identical before and after the step (Phase 12):

- M1 `m1_subject_endmarks.joblib` — `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E`
- M2 `m2_next_semester_performance.joblib` — `6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012`
- M3 `m3_next_semester_at_risk.joblib` — `99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7`

## 16. Database side effects

**None.** The contract performs no DB reads/writes. Verification uses only
in-memory frames built from real CSV mirrors; no rows were inserted or modified.

## 17. Limitations

- **OFFLINE ONLY.** This is not a deployed service, API, or UI.
- M3 remains **BLOCKED**; nothing here grants M3 production approval or
  promotion. Its scoring is available only via the explicit offline flag and
  still reports `prediction_available=False`.
- M2 percentage/SGPA outputs are returned as the model/runtime emit them (the
  existing contract applies its own bounds); no new thresholds were added.
- M1 readiness reflects the existing offline-scoring readiness; it is **not**
  approval for production/API/student-facing use.
- Lint tooling (flake8/ruff) is not present in the ml venv; `py_compile` passes.

## 18. Exact next single step

**STOP.** Do not build an API, dashboard, UI, or GenAI in this step.

The **next separate milestone** is:

> **READ-ONLY BACKEND PREDICTION SERVICE / API CONTRACT** — a future step that
> must consume this unified offline inference contract rather than create another
> inference implementation.

---

**Explicit statements (as required):**

- This is **OFFLINE ONLY**.
- **No API** was built.
- **No dashboard** was built.
- **No GenAI** was built.
- **No database writes** occurred.
- **No model training** occurred.
- **M3 remains blocked**.
- **No production approval** was granted.

## Final verdict

```
UNIFIED_OFFLINE_INFERENCE_CONTRACT_READY
```
