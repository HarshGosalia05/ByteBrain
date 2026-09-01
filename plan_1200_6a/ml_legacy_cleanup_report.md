# M1/M2/M3 Legacy Cleanup Report (V2-only Production UI)

- **Scope:** Phase 1 of the "Final ML Cleanup + M1/M2/M3 V2 Production UI Integration" task.
- **Approved scope (user decision):** Frontend V2-only + archive code, keep V1 backend. The active
  M1/M2/M3 UI is now V2-only; obsolete zero-reference files are deleted; all V1 runtime backend and
  ML-infra files that still serve `/predict/insights` (M4 + explanations) are KEPT.

## 1. What was deleted (zero-reference / archive-obsolete)

### Frontend — legacy M1/M2/M3 card components (replaced by V2 in the active UI)
- `components/student/ml-insights/m1-insights-card.tsx`
- `components/student/ml-insights/m2-insights-card.tsx`
- `components/student/ml-insights/m3-insights-card.tsx`
- `components/student/ml-insights/factor-list.tsx` (used only by legacy M1/M2/M3 cards)
- `components/student/ml-insights/signal-list.tsx` (used only by legacy M1/M2/M3 cards)
- `components/faculty/ml-insights/m1-insights-card.tsx`
- `components/faculty/ml-insights/m2-insights-card.tsx`
- `components/faculty/ml-insights/m3-insights-card.tsx`
- `components/faculty/ml-insights/m3-faculty-review.tsx` (used only by faculty M3 legacy card)

All was confirmed via grep to be referenced ONLY by the two grids
(`components/student/ml-insights/ml-insights-grid.tsx` and
`components/faculty/ml-insights/faculty-ml-insights-grid.tsx`), which were edited to drop the legacy
imports and render the V2 cards + M4 cards. `model-card.tsx`, `insight-unavailable.tsx`, and
`input-details.tsx` remain (M4 + shared card scaffolding still use them).

### ML — obsolete standalone verification / sandbox scripts (zero Python references)
Deleted the following V1-era manual verification and ad-hoc scripts. Grep confirmed **no runtime or
test `.py` file imports any of these**; matches are only internal function names
(`verify_no_leakage`, `_verify_checks`) or historical documentation references.

- `ml/verify_feature_engineering.py`, `ml/verify_m1.py`, `ml/verify_m1_multi_holdout.py`,
  `ml/verify_m1_readiness.py`, `ml/verify_m1_temporal.py`, `ml/verify_v1_baseline_m3.py`,
  `ml/verify_v1_cohort_expansion.py`, `ml/verify_v1_dataset.py`,
  `ml/verify_v1_etl_second_cohort_readiness.py`, `ml/verify_v1_feedback_audit.py`,
  `ml/verify_v1_inference_contract.py`, `ml/verify_v1_label_builder.py`,
  `ml/verify_v1_later_cohort_gate.py`, `ml/verify_v1_m2_regression.py`,
  `ml/verify_v1_m3_cohort_expansion.py`, `ml/verify_v1_m3_experiment.py`,
  `ml/verify_v1_m3_validation_gate.py`, `ml/verify_v1_model_improvement.py`,
  `ml/verify_v1_training_dataset.py`, `ml/run_m2_m3_cohort_expansion.py`, `ml/test_imports.py`.

  (21 files total.) The historical `plan_25_08/*.md` reports that named some of these scripts remain
  in the repo for audit value. Note: `ml/src/features/v1_inference_contract.py` and
  `ml/src/features/v1_ml_readiness_audit.py` are KEPT — they are runtime imports, not obsolete.

## 2. What was KEPT (V1 runtime backend — actively serving, per approved scope)

The following remain untouched and registed/imported at runtime:
- `backend/app/api/v1/predict.py` — legacy `/predict/m1|m2|m3|m4`, `/predict/insights/{id}`,
  `/predict/persist` routes still registered.
- `ml/src/registry.py` (load_model m1/m4 consumed by
  `backend/app/services/prediction_generation_service.py`), `ml/src/inference.py`,
  `ml/src/explain.py`, `ml/src/prediction_service.py`, `ml/src/prediction_persistence.py`.
- `ml/src/features/v1_inference_contract.py`, `ml/src/features/v1_ml_readiness_audit.py`.
- `ml/src/m1/{config,data,readiness,train_m1,temporal}.py`, `ml/src/m2/config.py`,
  `ml/src/m3/config.py`, and legacy artifacts
  `ml/artifacts/models/{m1_subject_endmarks,m2_next_semester_performance,m3_next_semester_at_risk}.joblib`.
- Backend `tests/` that mock `ml.src.registry.load_model`, and the ML preservation tests
  (`tests/test_v1_*.py`, `tests/test_registry.py`, `tests/test_inference.py`, etc.).

Retirement decision from `plan_1200_6a/ml_old_vs_v2_comparison.md`:
**ARCHIVE** old M1/M2/M3 artifacts + reports; **BLOCK** `ml/src/retrain_m3.py`; KEEP/PROMOTE V2.

## 3. Verification after cleanup
- `npx tsc --noEmit` → PASS (exit 0).
- `npm run test:frontend` → 161/161 pass.
- ML suite `..\backend\venv\Scripts\python.exe -m pytest tests/` → 713 passed.
- ML V2 suite (`v2/*/tests/`) → 128 passed.
- Backend V2 tests (`test_m1v2/m2v2/m3v2_prediction.py`) → 94 passed.

## 4. Status codes
- **LEGACY CLEANUP:** PASS — active UI is V2-only for M1/M2/M3, zero-reference obsolete files
  removed, V1 runtime backend kept per approved scope.