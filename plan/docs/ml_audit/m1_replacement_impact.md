# M1 Replacement Impact Analysis — New "Clean M1_v3"

**Task phase 23/24 of the audit.** Analysis of what happens when the external **NEW Clean M1_v3** package is integrated. This was the pre-migration forward-looking impact analysis.

> **STATUS (2026-09-07):** the migration is **COMPLETE**. The Clean M1_v3 package (`ml/M1_v3_CampusX_package/`, model `m1_v3_clean`) is integrated and active; the old synthetic `ml/v3/m1_subject_prediction/` was deleted. See [m1_v3_clean_replacement_report.md](./m1_v3_clean_replacement_report.md) and the updated [model_inventory.md](./model_inventory.md). The forward-looking analysis below is retained for historical context.

## A. Existing ingredients the new package must interoperate with

### A1. Feature availability for the production cohort (the hard constraint)
Confirmed usable inputs (9 + 2 computable):
`internal_marks, mid_sem_marks, credits, semester_no, subject_type, is_male, prior_avg_sgpa, prior_avg_attendance, prior_n_sems`
`pre_endsem_assessment_pct = (internal+mid)/70×100`, `sgpa_drift_latest = sgpa − LAG(sgpa)`

Unavailable for STU000% (80 students): `attendance_weekly*`, `learning_activity*`, `lifestyle*`, `assignment_score`, `quiz_avg_marks`, `submission_delay_days`, `subject_domain`.

**Conclusion:** A clean M1_v3 limited to the available set can predict for all 80 students. Any contract reaching beyond it returns NO_DATA for everyone (same trap M1 V2 is in).

### A2. Existing M1 V3 (synthetic) as a shape template
The existing package gives the expected layout for a clean package:
- `ml/v3/m1_subject_prediction/`: `artifacts/` (`m1_synthetic_v1.joblib`), `inference/predictor.py` (FEATURE_COLS=8, TARGET 0–70, PASS_THRESHOLD=30), `training/train.py`, `tests/test_m1_synthetic.py`. **No `config.py`** in the existing V3 (constants inline in predictor) — a clean package should add proper `config.py` + `preprocessing/pipeline.py` like V2 to keep contracts testable.
- Artifact schema (dict): `model`, `preprocessor` (ColumnTransformer), `feature_columns`, `numeric_columns`, `categorical_columns`, `target`, `target_min`, `target_max`, `pass_threshold`, `metadata` (with `leakage_audit`, `production_compatibility`).
- Security note: V3 dataset metadata points outside repo (`C:\Users\HET SHAH\ByteBrain\Dummy\...csv`); a clean package should ship its training provenance inside the artifact metadata alone.

## B. Impact surfaces if a new Clean M1_v3 is integrated

### B1. Backend (must change)
| File | Change type |
|---|---|
| `backend/app/api/v1/predict.py` | New/re-pointed endpoint (e.g. `/predict/m1v3clean/{student_id}` or serve-in-place of `/predict/m1v3`); keep `authorize_prediction_access` |
| `backend/app/services/` | New service (mirror `M1V3PredictionService`: sys.path insert, artifact load, readiness guard, leakage re-check) |
| `backend/app/services/prediction_generation_service.py` | `resolve_model_version` for the new artifact's version field so persisted rows are distinguishable |
| `backend/tests/test_m1v2_prediction.py` / new `test_m1v3clean_prediction.py` | mirror V3 service tests |

### B2. Frontend (must change)
| File | Change type |
|---|---|
| `lib/student-api.ts` `getStudentM1V3` (:653) | point to new endpoint / accept new type |
| `lib/m1v3-prediction.ts` | typed response for clean model |
| `app/student/ml-insights/page.tsx` | `SemesterTrendSection` + `MlInsightsSection` call sites (M1V3-preferred merge logic) |
| `components/student/ml-insights/m1v3-card.tsx` | render clean-model fields or reuse `ModelCard` |
| `lib/student/student-api.test.ts`, `lib/student-api.test.ts` | contract tests |

### B3. Chatbot (likely NO change)
- `student_prediction_explanation_tool` reads `ml_predictions.get_latest(student_id,"m1")` — version-agnostic; a persisted clean M1_v3 surfaces automatically under `model_id="m1"` with `model_kind="ml"`.
- G0 boundary unaffected. No orchestrator registry change.

### B4. Faculty / Admin (only if persisted)
- Faculty ml-insights + Admin ML-intelligence read persisted rows by type; clean rows just add to history (append-only), `model_version` differentiates.
- No schema change to `ml_predictions`.

### B5. Grade bands / semantics decision
- V2 maps marks→grades (`O/A+/A/B+/B/C/Fail`, pass bandwidth 26–30). A clean model must either adopt the same bands or define its own and update the card/verbalizers. **Must be explicit — silent reuse risks grade drift.**

## C. Feature-level compatibility to verify when the package arrives
1. Compare artifact `feature_names`/`feature_columns` vs the 9+2 available production set → count overlapping and missing.
2. Confirm OHE vocabulary (subject_type/domain/department/gender) matches `ml/src/feature_config.py`/`features.py` conventions so builder output aligns.
3. Confirm `attendance_percentage` source table (attendance vs attendance_weekly) — the existing V3 used the former; `attendance_weekly` is empty for 80 students.
4. Confirm target bounds [0,70] and pass_threshold semantics (0–70 scale, PASS_THRESHOLD=30 in existing V3).
5. Confirm artifact pickles resolve without `sys.path` hacks OR document the package path to add to the service.

## D. Risks & mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Clean model trains with features unavailable in production | HIGH (if contract > 9+2 set) | CRITICAL (all-NO_DATA / imputed false scores) | Gate on feature-overlap test; keep NO_DATA honesty contract |
| Metric confusion: synthetic vs real trained models compared unfairly | HIGH | MEDIUM | Compare only same-provenance; document training data in metadata |
| Duplicate M1 endpoints confuse consumers | MEDIUM | MEDIUM | Versioned endpoint naming; `ml_legacy_cleanup` pattern |
| Clean model used for chatbot without persistence | LOW | MEDIUM | Persist via `POST /predict/persist/m1/...` so all read surfaces stay consistent |
| Artifact version drift breaks `resolve_model_version` | LOW | MEDIUM | Single source of truth in artifact metadata (`model_version`) |

## E. Recommended integration order (for when approved)
1. Provide the Clean M1_v3 package + feature contract → verify overlap vs section C (this audit's PHASE 24-input).
2. Add package under `ml/v3/m1_subject_prediction_clean/` (or replace existing v3) with `config.py`/`pipeline.py`/tests.
3. Add backend service + endpoint (RBAC-gated) + NO_DATA semantics + 503-on-missing-artifact.
4. Update `lib` types + page/card, run `lib` tests.
5. Enable persistence keyed `m1` with clean `model_version`; chatbot/UI read surfaces update automatically.
6. Run backend + lib test suites; verify `git diff` shows no unintended source changes.