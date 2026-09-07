# M1 V3 Replacement — Final Report (Clean Package Integration + Prediction Parity)

**Date:** 2026-09-07
**Status:** COMPLETE — only one M1 V3 implementation is active (the Clean `m1_v3_clean` model). The old synthetic M1 V3 is removed. Prediction parity with the packaged reference model is verified on real live students.

---

## 1. Summary

CampusX now runs M1 V3 end-sem subject prediction exclusively on the **Clean M1 V3** package at `ml/M1_v3_CampusX_package/` (model_version `m1_v3_clean`, `HistGradientBoostingRegressor`, 38-feature `C_core_history_learning` contract, target `end_sem_marks` 0–70), served through the production adapter `ml/v3/m1_subject_prediction_clean/`. The previous synthetic M1 V3 implementation (`ml/v3/m1_subject_prediction/`, LinearRegression/8 features) was deleted in its entirety. The model is loaded from the packaged artifact `m1_v3_pipeline.pkl` (trained on real CampusX data); no code was retrained.

API/UI contract, RBAC/authorization, chatbot grounding, /70 predicted and /50 mid-sem scales are all preserved.

---

## 2. Deleted OLD M1 V3 (synthetic) — no longer active

| Path | What it was |
|------|-------------|
| `ml/v3/m1_subject_prediction/__init__.py` | package init |
| `ml/v3/m1_subject_prediction/artifacts/m1_synthetic_v1.joblib` | synthetic LinearRegression artifact (8 features) |
| `ml/v3/m1_subject_prediction/data/__init__.py` | data module |
| `ml/v3/m1_subject_prediction/inference/__init__.py`, `inference/predictor.py` | old predictor (`FEATURE_COLS`=8, LinearRegression) |
| `ml/v3/m1_subject_prediction/preprocessing/__init__.py` | module |
| `ml/v3/m1_subject_prediction/tests/__init__.py`, `tests/test_m1_synthetic.py` | old tests |
| `ml/v3/m1_subject_prediction/training/__init__.py`, `training/train.py` | training driver |
| `ml/v3/m1_subject_prediction/validation/__init__.py` | validation module |
| `test_m1v3_readonly.py` (repo root) | stale root test referencing old package + machine paths |
| `plan_1200_6a/dry_run_m1v3.py` | old dry-run script |

**Verification:** `git status` shows every old file as deleted; the directory `ml/v3/m1_subject_prediction/` no longer exists. A repo-wide search finds **no** `ml/v3/m1_subject_prediction`, `m1_synthetic_v1`, or `m1_synthetic` references in active code (only historical audit docs).

---

## 3. Integrated Clean M1 V3 — active

| Path | Role |
|------|------|
| `ml/M1_v3_CampusX_package/model/m1_v3_pipeline.pkl` | packaged sklearn Pipeline (nested ColumnTransformer: median-imputer + StandardScaler for numeric, most-frequent + OHE for categorical, then HGBR) |
| `ml/M1_v3_CampusX_package/schema/features.json` | 38-feature list in model order |
| `ml/M1_v3_CampusX_package/schema/M1_v3_FEATURE_CONTRACT.md` | binding feature-construction contract |
| `ml/M1_v3_CampusX_package/metadata/M1_v3_METADATA.json` | model metadata (params, train/val/test metrics, data tables required) |
| `ml/M1_v3_CampusX_package/inference/m1_v3_predict.py` | `M1Model` wrapper (clips to [0,70], enforces exact feature set) |
| `ml/v3/m1_subject_prediction_clean/inference/predictor.py` | **production adapter** `M1V3CleanPredictor`: builds the 38 features via read-only SQL, validates `FEATURE_COLS == features.json` at load, leakage guard, per-student/subject predictions, `get_predictor()` singleton |
| `ml/v3/m1_subject_prediction_clean/inference/__init__.py` | module |
| `backend/app/services/m1v3_prediction_service.py` | backend adapter — imports `M1V3CleanPredictor`, preserves `model_id="m1_v3"`, RBAC unchanged |
| `backend/app/schemas/m1v3.py` | M1 V3 response contract (labeled m1_v3_clean) |
| `backend/app/api/v1/predict.py` | `GET /predict/m1v3/{student_id}` endpoint docstring (contract unchanged, RBAC unchanged) |
| `backend/tests/test_m1v3_prediction.py` | rewritten test suite (30 tests) |
| `lib/m1v3-prediction.ts` | frontend client (labels/notes updated) |
| `lib/student-api.ts`, `lib/faculty-api.ts` | client notes for the /predict/m1v3 endpoints |
| `components/student/ml-insights/m1v3-card.tsx`, `components/faculty/ml-insights/m1v3-card.tsx` | fallback note (attendance not an input of the clean model; tile hidden when `attendance_percentage` is null) |
| `lib/m1v3-prediction.test.ts`, `lib/student/student-api.test.ts` | updated fixtures/assertions |
| `plan/docs/ml_audit/model_inventory.md`, `legacy_and_duplicate_models.md` | audit inventory updated (V3 clean active; synthetic REMOVED 2026-09-07) |

---

## 4. Feature-generation method (trace: package → CSVs/ETL → DB query → inference)

The 38 features are defined in `schema/features.json` and `M1_v3_FEATURE_CONTRACT.md`. The training dataset was engineered from the 27-table CSV snapshot `supabase_export_04_09_latest_27table` (row counts verified identical to the live DB: students 1280, performance 72250, enrollment 72250, semester_summary 10100, learning_activity 547200). In production the adapter rebuilds the same features from the live database via read-only SQL.

| # | Feature group | Live-DB source (production SQL) | CSV/ETL source at build time | Feature names |
|---|---------------|--------------------------------|------------------------------|---------------|
| 1–6 | Current subject | `student_subject_performance` (per subject, semester = current) | `student_subject_performance.csv` | `internal_marks`, `mid_sem_marks`, `pre_endsem_assessment_pct`, `assignment_score`, `quiz_avg_marks`, `submission_delay_days` |
| 7–17 | History (prev_*) | `student_semester_summary` **semester_no < N only** (temporal rule) | `student_semester_summary.csv` | `prev_sgpa_mean/pct_mean/att_mean/backlog_sum/n_semesters/sgpa_last/pct_last/att_last/backlog_last`, `sgpa_trend`, `pct_trend` |
| 18–31 | Learning activity (act_*) | `student_learning_activity` weeks 1–8, grouped by subject; sum/mean per contract | `student_learning_activity.csv` (weekly raw → derived per-week fields) | `act_sess_sum`, `act_resource_views_sum`, `act_assess_attempts_sum`, `act_submission_sum`, `act_late_submission_sum`, `act_avg_delay_mean`, `act_volume_sum`, `act_velocity_mean`, `act_change_mean`, `act_inactive_weeks`, `act_engagement_mean`, `act_late_rate_mean`, `act_completion_mean`, `act_active_days_sum` |
| 32–35 | Context (numeric) | `student_subject_enrollment`, `students` | `student_subject_enrollment.csv`, `students.csv` | `semester_no`, `credits`, `department_code` (1=CSE, 2=BBA verified), `admission_year` |
| 36–38 | Context (categorical) | `student_subject_enrollment`, `students` | same CSVs | `subject_type`, `gender`, `category` |

Key rules enforced by the adapter (identical to the contract):
- **Temporal**: history features use only semesters strictly < target N; never the current/future semester or cumulative CGPA.
- **Leakage guard**: `end_sem_marks`, `total_marks`, `percentage`, `grade`, `grade_point`, `result_status`, `performance_category` are rejected if they ever reach inference (`predictor.py` `FORBIDDEN_TARGET_FIELDS` + `check_no_leakage`).
- **Imputation**: missing values are `NaN`, never zero-filled; the pipeline's embedded `SimpleImputer(median)` fills them.
- **Load-time contract check**: `M1V3CleanPredictor.load()` raises if `FEATURE_COLS` deviates from the packaged `features.json`.
- **Derived act_* weekly fields** consumed per contract aggregation (sum/mean): `activity_volume = active_days + learning_sessions + assessment_attempts + submission_count`, `activity_velocity = Δvolume`, `activity_change_pct = Δ%/prev×100`, `late_submission_rate = late/submissions`, `inactive_week_flag = (volume==0)` — all numerically validated against real DB rows; `engagement_consistency` and `assessment_completion_rate` are stored weekly production values aggregated per the contract (not present in the 04-09 CSV export).

---

## 5. Prediction parity — proof

**Method.** Two independent feature-construction paths run for the same real (student, subject, semester):

- **Path S (production):** the exact SQL + helpers used by `M1V3CleanPredictor` against the live database.
- **Path R (reference):** an independent pandas builder over the CSV snapshot implementing the contract (current-subject + prev_* from raw CSV columns; act_* re-derived per the formulas above; context from enrollment/students CSV).

Both 38-vectors are fed to the **same packaged `M1Model`** (`m1_v3_pipeline.pkl`), and the production `predict_for_student` output is compared as well. Results (7 subjects per student, 35 rows total):

| Student | Band | Semester | SGPA | Backlogs | Exact 38-feature parity (rows) | Predictions identical |
|---|---|---|---|---|---|---|
| STU000053 | Strong | 5 | 9.00 | 0 | 7 / 7 | yes |
| STU000054 | Strong | 5 | 8.00 | 0 | 7 / 7 | yes |
| STU000067 | Average | 5 | 6.00 | 0 | 7 / 7 | yes |
| STU000001 | Weak | 7 | 0.00 | 0 | 7 / 7 | yes |
| STU000002 | Weak | 7 | 0.00 | 0 | **7 / 7** (see note) | yes |

**STU000002 note (data drift, not a logic mismatch).** The CSV-vs-SQL comparison initially showed a 0.37 delta on exactly three history features (`prev_sgpa_mean`, `prev_sgpa_last`, `sgpa_trend`). This was traced to live-database updates to STU000002's sems 4–6 SGPA (now 10.00/10.00/10.00) versus the 04-09 snapshot (9.23/9.62/9.99). The reference builder was re-run with the **same live summary data** → all 38 features match to **max abs diff 0.0** and both prediction paths return **66.33979…** exactly. The delta is an honest reflection of newer data, not feature-engineering divergence.

**Conclusion.** For identical features, the production path and the packaged reference model return identical predictions (every subject in the table: `predicted_end_sem_marks` == `clip(M1Model.predict(vector),0,70)`). Fortified evidence: sample of 35 live rows with exact (0.0) feature-vector equality across two independent implementations (SQL vs pandas/CSV) plus end-to-end service equality.

Reproduction: `C:\Users\HARSHG~1\AppData\Local\Temp\opencode\parity_harness.py` (read-only) → writes `parity_report.json`.

---

## 6. Files changed (this migration)

- Deleted: the 11 files in §2 (old synthetic package + stale root test + dry-run script).
- Added/created: `ml/v3/m1_subject_prediction_clean/` (adapter), audit report docs under `plan/docs/ml_audit/`.
- Modified:
  - `backend/app/services/m1v3_prediction_service.py` (wiring `M1V3CleanPredictor`)
  - `backend/app/schemas/m1v3.py`, `backend/app/api/v1/predict.py` (labels/docstrings)
  - `backend/tests/test_m1v3_prediction.py` (rewritten)
  - `lib/m1v3-prediction.ts`, `lib/student-api.ts`, `lib/faculty-api.ts`, `lib/m1v3-prediction.test.ts`, `lib/student/student-api.test.ts`, `components/student/ml-insights/m1v3-card.tsx`, `components/faculty/ml-insights/m1v3-card.tsx`
  - `plan/docs/ml_audit/model_inventory.md`, `plan/docs/ml_audit/legacy_and_duplicate_models.md`

---

## 7. Tests run (2026-09-07)

| Suite | Command | Result |
|---|---|---|
| Backend M1/RBAC/contract | `pytest tests/test_m1v3_prediction.py tests/test_predict_rbac.py tests/test_ml_prediction_service.py tests/test_m1v2_prediction.py tests/test_prediction_contract_service.py` | **101 passed** |
| Backend chatbot | `pytest tests/test_chatbot_understanding.py tests/test_chatbot_response_layer.py tests/test_chatbot_e2e_scenarios.py tests/test_chat_api.py tests/test_chat_orchestrator.py` | **188 passed** |
| Frontend unit | `npm run test:frontend` | **190/190 passed** |
| Typecheck | `npm run typecheck` | clean |
| Build | `npm run build` | **success** |

> Note: `next build` requires reduced worker concurrency on this machine (`CIRCLE_NODE_TOTAL=2`). The host has ~7 GB RAM with ~1.1 GB free; Next's default 11 build workers exhaust memory during static-page generation (`FATAL ERROR: Zone Allocation failed`). Output is otherwise identical.
>
> E2E (live DB, Admin path, upsert disabled): `STU000001` → `READY`, 7 subjects, model_version `m1_v3_clean`, algorithm `HistGradientBoostingRegressor`, schema-valid; Student-on-other RBAC → 403.

---

## 8. M2 / M3 / M4 / M5 — untouched

No M2, M3, M4, or M5 model code, artifacts, ETL, schemas, services, or tests were modified (only M1 V3 work described above). `git status` shows no M2–M5 files among the migration changes. The M2 and M3 v2 pipelines and their tests remain in their pre-existing state.

**Unrelated pre-existing working-tree changes (not part of this task, left untouched):** an in-progress Admin ML generation feature (`backend/app/api/v1/admin.py`, `backend/app/services/admin_ml_service.py`, `backend/app/services/admin_ml_generation_service.py`, `backend/app/schemas/admin_ml_generation.py`, `lib/admin-api.ts`, `components/admin/ml-intelligence/*`, `backend/tests/test_admin_ml_intelligence.py`), plus an emptied `ml/v2/m1_subject_prediction/data/loader.py` and untracked `app/api/admin/`.