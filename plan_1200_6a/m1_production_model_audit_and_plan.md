# M1 Production Model Audit & Implementation Plan

**Date:** 2026-09-01
**Scope:** Complete audit of M1 model stack for production deployment to 80 students (STU000001–STU000080)
**Status:** AUDIT COMPLETE — BLOCKED (requires decision)
**Author:** ByteBrain Engineering

---

## Executive Summary

M1 V2 **cannot serve the 80 production students** in its current form. The model was trained on 1,200 CSE 6A students with complete feature data across 8 data sources. The 80 production students are missing **13 of 25 base features** — including attendance weekly, learning activity, lifestyle survey, assignment scores, and quiz marks. These are not edge cases; they are structural data gaps.

**Verdict: M1 V3 TRAINING BLOCKED** until a decision is made on data acquisition or model adaptation strategy.

---

## Phase 1: Model Architecture Trace

### M1 V2 Code Path (Complete)

| Step | File | Function | Purpose |
|---|---|---|---|
| 1 | `config.py` | Constants | Feature lists, cohort filter `STU6A`, target `end_sem_marks` |
| 2 | `data/loader.py` | `SupabaseLoader.load_sync()` | SQL queries for 8 tables, filtered by `LIKE 'STU6A%'` |
| 3 | `features/builder.py` | `check_joins()` | FK integrity, grain uniqueness |
| 4 | `features/builder.py` | `build_feature_matrix()` | 7-step join: perf→enr→stu→att→learn→life→prior |
| 5 | `preprocessing/pipeline.py` | `select_features()` | 25 base → OHE/ordinal/binary encoding → ~39 columns |
| 6 | `training/train.py` | `main()` | GroupKFold(5) + temporal holdout + model selection |
| 7 | `training/train.py` | `fit_final_model()` | Final fit on sems 1–7 |
| 8 | `inference/predictor.py` | `predict_for_student()` | DB fetch → feature build → predict |

### M1 V2 Feature Contract (25 Base Features)

| # | Feature | Source Table | Type | 80-Student Availability |
|---|---|---|---|---|
| 1 | `internal_marks` | `student_subject_performance` | numeric 0–20 | **100%** ✓ |
| 2 | `mid_sem_marks` | `student_subject_performance` | numeric 0–50 | **100%** ✓ |
| 3 | `pre_endsem_assessment_pct` | `student_subject_performance` | numeric 0–100 | **0%** (computable: `(internal+mid)/70×100`) |
| 4 | `assignment_score` | `student_subject_performance` | numeric 0–100 | **0%** ✗ |
| 5 | `quiz_avg_marks` | `student_subject_performance` | numeric 0–100 | **0%** ✗ |
| 6 | `submission_delay_days` | `student_subject_performance` | numeric | **0%** ✗ |
| 7 | `att_total_pct` | `attendance_weekly` | numeric | **NO DATA** ✗ |
| 8 | `att_rolling_4w_mean` | `attendance_weekly` | numeric | **NO DATA** ✗ |
| 9 | `att_velocity_latest` | `attendance_weekly` | numeric | **NO DATA** ✗ |
| 10 | `credits` | `student_subject_enrollment` | numeric | **100%** ✓ |
| 11 | `semester_no` | `student_subject_performance` | numeric | **100%** ✓ |
| 12 | `activity_volume_total` | `student_learning_activity` | numeric | **0 rows** ✗ |
| 13 | `avg_engagement_consistency` | `student_learning_activity` | numeric 0–1 | **0 rows** ✗ |
| 14 | `avg_assessment_completion_rate` | `student_learning_activity` | numeric 0–1 | **0 rows** ✗ |
| 15 | `avg_late_submission_rate` | `student_learning_activity` | numeric 0–1 | **0 rows** ✗ |
| 16 | `subject_type` | `student_subject_enrollment` | OHE | **100%** ✓ |
| 17 | `subject_domain` | `student_subject_performance` | OHE | **0%** ✗ |
| 18 | `is_male` | `students` | binary | **100%** ✓ |
| 19 | `stress_ordinal` | `student_lifestyle_survey` | ordinal | **NO DATA** ✗ |
| 20 | `study_hours_per_week` | `student_lifestyle_survey` | numeric | **NO DATA** ✗ |
| 21 | `prior_avg_sgpa` | `student_semester_summary` | derived | **100%** ✓ |
| 22 | `sgpa_drift_latest` | `student_semester_summary` | derived | **0%** (computable: `sgpa - LAG(sgpa)`) |
| 23 | `prior_backlog_cumulative` | `student_semester_summary` | numeric | **0%** ✗ |
| 24 | `prior_avg_attendance` | `student_semester_summary` | derived | **100%** ✓ |
| 25 | `prior_n_sems` | `student_semester_summary` | count | **100%** ✓ |

### Feature Availability Summary

| Category | Count | Features |
|---|---|---|
| **Fully available** | 9 | internal_marks, mid_sem_marks, credits, semester_no, subject_type, is_male, prior_avg_sgpa, prior_avg_attendance, prior_n_sems |
| **Computable** | 2 | pre_endsem_assessment_pct, sgpa_drift_latest |
| **Genuinely unavailable** | 13 | assignment_score, quiz_avg_marks, submission_delay_days, att_total_pct, att_rolling_4w_mean, att_velocity_latest, activity_volume_total, avg_engagement_consistency, avg_assessment_completion_rate, avg_late_submission_rate, stress_ordinal, study_hours_per_week, prior_backlog_cumulative |
| **Unavailable (OHE)** | 1 | subject_domain |

**Result: 11/25 features available, 14/25 missing. The model cannot produce valid predictions.**

---

## Phase 2: Target Availability Audit

### `end_sem_marks` Labels for 80 Production Students

| Semester | Total Rows | Labeled | NULL | Students with Labels |
|---|---|---|---|---|
| 1 | 610 | 610 (100%) | 0 | 80/80 |
| 2 | 610 | 610 (100%) | 0 | 80/80 |
| 3 | 660 | 660 (100%) | 0 | 80/80 |
| 4 | 610 | 610 (100%) | 0 | 80/80 |
| 5 | 610 | 400 (66%) | 210 | 50/80 |
| 6 | 400 | 400 (100%) | 0 | 50/80 |
| 7 | 350 | 1 (<1%) | 349 | 1/80 |

**Total labeled rows: 3,291**

### Key Observations

1. **Semesters 1–4**: Fully labeled for all 80 students — this is the reliable training data
2. **Semester 5**: Only 50 students labeled (30 students have NULL end_sem_marks) — data entry incomplete
3. **Semester 6**: Only 50 students even have enrollment/performance records (30 students graduated/deferred)
4. **Semester 7**: Only 1 labeled row — essentially no production labels exist

### Training Feasibility

| Training Set | Rows | Students | Feasibility |
|---|---|---|---|
| Semesters 1–4 only | 2,540 | 80 | ✓ Possible but limited |
| Semesters 1–5 (with NULLs) | 2,940 | 80 | ⚠ 210 NULLs need handling |
| Semesters 1–6 | 3,291 | 80 | ⚠ Only 50 students in sem 6 |

---

## Phase 3: Data Source Deep Dive

### 3.1 `student_subject_performance` (3,850 rows, 80 students)

| Column | Non-null | % | Notes |
|---|---|---|---|
| `internal_marks` | 3,850 | 100% | ✓ |
| `mid_sem_marks` | 3,850 | 100% | ✓ |
| `end_sem_marks` | 3,291 | 85% | NULLs in sem 5 (210) and sem 7 (349) |
| `pre_endsem_assessment_pct` | 0 | 0% | Synthetic column — can compute as `(internal+mid)/70×100` |
| `assignment_score` | 0 | 0% | Synthetic column — genuinely missing |
| `quiz_avg_marks` | 0 | 0% | Synthetic column — genuinely missing |
| `submission_delay_days` | 0 | 0% | Synthetic column — genuinely missing |
| `subject_domain` | 0 | 0% | Missing — no source to derive |

### 3.2 `student_learning_activity` (0 rows for STU000%)

**Zero rows exist.** This table was populated only for the 1,200 CSE 6A students via the 6A-specific ETL. The 80 production students have no learning activity data and no alternative source.

### 3.3 `attendance_weekly` (0 rows for STU000%)

**Zero rows exist.** Same situation as learning activity — only populated for 6A students.

### 3.4 `student_lifestyle_survey` (0 rows for STU000%)

**Zero rows exist.** The table structure exists (`survey_id, student_id, semester_no, sleep_hours_per_day, commute_time_mins, study_hours_per_week, mental_stress_level, extracurricular_hours_per_week`) but has no data for STU000% students.

### 3.5 `student_semester_summary` (550 rows, 80 students)

| Semester | Rows | sgpa_nn | att_nn | backlog_events_nn | backlog_count_nn | drift_nn |
|---|---|---|---|---|---|---|
| 1 | 80 | 80 | 80 | 0 | 80 | 0 |
| 2 | 80 | 80 | 80 | 0 | 80 | 0 |
| 3 | 80 | 80 | 80 | 0 | 80 | 0 |
| 4 | 80 | 80 | 80 | 0 | 80 | 0 |
| 5 | 80 | 80 | 80 | 0 | 80 | 0 |
| 6 | 50 | 50 | 50 | 0 | 50 | 0 |
| 7 | 50 | 50 | 50 | 0 | 50 | 0 |

- `semester_sgpa`: 100% — ✓ (all 80 students, all semesters)
- `semester_attendance_percentage`: 100% — ✓
- `cumulative_backlog_events`: 0% — ✗ (all NULL)
- `backlog_count`: 100% — ✓
- `sgpa_drift`: 0% — ✗ (all NULL, but computable as `sgpa - LAG(sgpa)`)

### 3.6 `student_subject_enrollment` (3,850 rows, 80 students)

- `credits`: 100% — ✓
- `subject_type`: 100% — ✓

### 3.7 `students` (80 rows)

- `gender`: 100% — ✓
- `current_semester`: 100% (range: 5–7)

---

## Phase 4: M1 V2 Inference Path Analysis

### Deployment Cohort Guard

```python
# predictor.py:275
if not student_id.startswith(deployment_prefix):
    return { "readiness_status": "NO_DATA", ... }
```

- `deployment_prefix = "STU6A"` (from metadata or config)
- All STU000xxx students are blocked → returns NO_DATA

### Feature Build Path (predictor.py:352–461)

For each subject in the student's current semester:

1. **Pre-exam signal check** (line 362): `pre_endsem_assessment_pct` must be non-null → **ALL 80 students FAIL this check** (column is 0% populated)
2. Even if we compute `(internal+mid)/70×100`, the following features would be NaN:
   - `att_total_pct`, `att_rolling_4w_mean`, `att_velocity_latest` — no attendance data
   - `activity_volume_total`, `avg_engagement_consistency`, `avg_assessment_completion_rate`, `avg_late_submission_rate` — no learning activity
   - `study_hours_per_week`, `stress_ordinal` — no lifestyle data
   - `subject_domain` — no domain data
   - `prior_backlog_cumulative` — all NULL

### What Would Happen If We Forced Prediction

If we bypassed the cohort guard and pre-exam signal check:
- 14 of 25 features would be NaN/0
- The M1Preprocessor would impute with training medians (from 6A data)
- The model would receive a **near-all-zero vector** with imputed values from a different population
- Prediction would be clipped to `[0, 70]` — likely producing a false low score (0.0 or near-minimum)
- **This is exactly the false "0.0/70 F At Risk" problem the guard was designed to prevent**

---

## Phase 5: M1 V1 vs V2 Comparison

| Aspect | M1 V1 (Legacy) | M1 V2 (Current) |
|---|---|---|
| Training data | Synthetic: 80 students, 3,293 rows | Real: 1,200 CSE 6A students, 68,400 rows |
| Reported MAE | 3.18 | 6.319 (CV), 6.302 (temporal) |
| Reported R² | 0.82 | 0.434 (CV), 0.423 (temporal) |
| Trustworthy? | **NO** — synthetic near-stationary data | **YES** — honest metrics on real data |
| Baseline beat? | N/A (no real baseline) | 25% better than mean predictor |
| Feature count | 12 (Stage A) + 7 (Stage B) | 25 base → ~39 after OHE |
| Target | `end_sem_marks` | `end_sem_marks` |
| Deployment cohort | STU000 (80 students) | STU6A (1,200 students) |

### Critical Insight

M1 V1's metrics are **untrustworthy** because the synthetic data has feature-target correlations of 0.86–0.99. The model was essentially interpolating a deterministic generator. M1 V2's higher MAE (6.3 vs 3.2) is NOT a regression — it's the honest measurement of a model trained on real, noisy data.

---

## Phase 6: What Would It Take to Serve 80 Students?

### Option A: Retrain M1 V3 on 80-Student Data

| Requirement | Status | Notes |
|---|---|---|
| Labeled data | **PARTIAL** | 2,540 labeled rows (sems 1–4) or 2,940 (sems 1–5 with NULLs) |
| Feature completeness | **11/25** | 14 features genuinely unavailable |
| Minimum viable feature set | **~10 features** | internal, mid, pre_exam, credits, sem, subject_type, is_male, prior_sgpa, prior_att, prior_n_sems |
| Expected performance | **Degraded** | Missing 56% of features → likely MAE > 8 (worse than mean baseline) |
| Validation | **Weak** | GroupKFold on 80 students (small N), no temporal holdout possible |
| Risk | **HIGH** | Small training set, feature-reduced model, different population |

**Verdict: NOT RECOMMENDED.** A model trained on 10/25 features from 80 students would be unreliable and likely worse than the mean baseline.

### Option B: Populate Missing Data Sources

| Data Source | What's Needed | Feasibility |
|---|---|---|
| `attendance_weekly` | Weekly attendance records for 80 students | Requires data entry from institution |
| `student_learning_activity` | LMS activity data | Requires LMS integration |
| `student_lifestyle_survey` | Self-reported survey | Requires survey administration |
| `assignment_score` | Assignment grades | Requires gradebook data |
| `quiz_avg_marks` | Quiz scores | Requires gradebook data |
| `subject_domain` | Subject classification | Can be derived from `subjects` table if `subject_code` mapping exists |

**Verdict: POSSIBLE but REQUIRES EXTERNAL DATA ACQUISITION.** This is an institutional data problem, not an ML problem.

### Option C: Accept NO_DATA for 80 Students (Recommended)

| Aspect | Impact |
|---|---|
| User experience | Students see "Prediction not available yet" with clear explanation |
| Data integrity | No false predictions, no fabricated scores |
| Technical debt | M1 V2 remains clean, no reduced-feature hack |
| Future path | When data is populated (semester progresses), predictions auto-enable |

**Verdict: RECOMMENDED.** The current NO_DATA response (after our fix) is honest and correct.

---

## Phase 7: Code Changes Already Made

### Backend (M1 V2 API)

| File | Change | Purpose |
|---|---|---|
| `backend/app/schemas/m1v2.py` | Added `reason: str \| None = None` | Backend can explain why prediction is unavailable |
| `backend/app/services/m1v2_prediction_service.py` | Removed ValueError for NO_DATA in `_guard_readiness` | NO_DATA returns 200, not 500 |
| `backend/app/api/v1/predict.py` | Removed `ValueError` → 404 mapping | Endpoint returns 200 with readiness_status |
| `ml/v2/m1_subject_prediction/inference/predictor.py` | Replaced cryptic "outside deployment cohort" with clear explanation | User sees actionable message |

### Frontend

| File | Change | Purpose |
|---|---|---|
| `lib/m1v2-prediction.ts` | Added `reason: string \| null` | Type matches backend response |
| `app/student/ml-insights/page.tsx` | Detects `NO_DATA` in 200 response | Handles new response format |
| `components/student/ml-insights/ml-insights-grid.tsx` | Added `m1v2Reason` prop | Displays backend reason to user |

### Tests

| File | Change | Purpose |
|---|---|---|
| `lib/student/student-api.test.ts` | Updated M1 V2 body + NO_DATA test | Matches new response format |
| `lib/faculty-api.test.ts` | Updated M1 V2 body + NO_DATA test | Matches new response format |
| `lib/admin-api.test.ts` | Updated M1 V2 body + NO_DATA test | Matches new response format |
| `backend/tests/test_m1v2_prediction.py` | Updated 8 tests for new behavior | Error handling + cohort guard tests |

---

## Phase 8: Training Data Requirements for M1 V3

### If Retraining Were Approved (NOT recommended now)

| Requirement | Minimum | Ideal |
|---|---|---|
| Students | 80 | 500+ |
| Labeled rows | 2,000+ | 10,000+ |
| Semesters per student | 3+ | 5+ |
| Feature completeness | 20/25 | 25/25 |
| Temporal holdout | Last semester | Last 2 semesters |
| GroupKFold folds | 3 | 5 |

### Minimum Viable Feature Set (10 features)

If forced to train on 80 students with available data:

```
Tier 1 (available):
  internal_marks, mid_sem_marks, pre_endsem_assessment_pct (computed),
  credits, semester_no, subject_type, is_male

Tier 2 (available):
  prior_avg_sgpa, prior_avg_attendance, prior_n_sems
```

**Expected MAE: >8.0** (worse than mean baseline of 8.413 on 6A temporal holdout)

---

## Phase 9: Recommendation

### Immediate (Now)

1. **Keep M1 V2 as-is** — no retraining, no artifact modification
2. **Keep NO_DATA response** for STU000xxx students — honest, correct, no false predictions
3. **No further code changes needed** — backend/frontend/tests already updated

### Short-Term (This Sprint)

4. **Do NOT attempt M1 V3 training** — insufficient data, insufficient features
5. **Document the gap** — the 80 students need institutional data (attendance, LMS, surveys) before ML predictions are meaningful

### Medium-Term (Next Quarter)

6. **Data acquisition project** — work with institution to populate:
   - `attendance_weekly` (weekly class attendance)
   - `student_learning_activity` (LMS engagement)
   - `student_lifestyle_survey` (self-reported survey)
   - `assignment_score`, `quiz_avg_marks` (gradebook)
7. **Re-evaluate after data population** — once features are available, M1 V3 training can proceed

### Long-Term

8. **M1 V3 training** — when data is available, train on combined 6A + 80-student data
9. **Cross-cohort validation** — validate on truly unseen students

---

## Phase 10: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Users see NO_DATA indefinitely | HIGH | MEDIUM | Clear messaging, data acquisition roadmap |
| Someone forces retraining on incomplete data | MEDIUM | HIGH | Code review, training pipeline guards |
| M1 V2 artifact is modified | LOW | CRITICAL | File integrity checks, deployment gates |
| 80 students get false predictions | LOW | CRITICAL | Cohort guard + pre-exam signal check (already fixed) |
| Data acquisition succeeds but model underperforms | MEDIUM | MEDIUM | Baseline comparison gates in training pipeline |

---

## Appendix A: Supabase Diagnostic Results

**Run:** 2026-09-01, live query against production Supabase

```
TARGET AVAILABILITY (end_sem_marks):
  Sem 1: 610 rows, 610 labeled, 0 NULL
  Sem 2: 610 rows, 610 labeled, 0 NULL
  Sem 3: 660 rows, 660 labeled, 0 NULL
  Sem 4: 610 rows, 610 labeled, 0 NULL
  Sem 5: 610 rows, 400 labeled, 210 NULL
  Sem 6: 400 rows, 400 labeled, 0 NULL
  Sem 7: 350 rows, 1 labeled, 349 NULL

FEATURE COLUMNS (student_subject_performance, 80 students):
  internal_marks: 3850/3850 (100%)
  mid_sem_marks: 3850/3850 (100%)
  pre_endsem_assessment_pct: 0/3850 (0%)
  assignment_score: 0/3850 (0%)
  quiz_avg_marks: 0/3850 (0%)
  submission_delay_days: 0/3850 (0%)
  subject_domain: 0/3850 (0%)

STUDENT LEARNING ACTIVITY: 0 rows
ATTENDANCE WEEKLY: NO DATA
LIFESTYLE SURVEY: NO DATA

STUDENT SEMESTER SUMMARY:
  sgpa: 100% all semesters
  att: 100% all semesters
  backlog_events: 0% all semesters
  backlog_count: 100% all semesters
  drift: 0% all semesters

TOTAL LABELED ROWS (all semesters): 3,291
```

---

## Appendix B: Files Modified in This Session

| File | Action | Lines Changed |
|---|---|---|
| `backend/app/schemas/m1v2.py` | Added `reason` field | +1 |
| `backend/app/services/m1v2_prediction_service.py` | Removed ValueError for NO_DATA | ~5 |
| `backend/app/api/v1/predict.py` | Removed ValueError→404 mapping | ~10 |
| `ml/v2/m1_subject_prediction/inference/predictor.py` | Updated reason message | ~10 |
| `lib/m1v2-prediction.ts` | Added `reason` type | +1 |
| `app/student/ml-insights/page.tsx` | NO_DATA detection in 200 | ~10 |
| `components/student/ml-insights/ml-insights-grid.tsx` | m1v2Reason prop | ~10 |
| `lib/student/student-api.test.ts` | Updated tests | ~10 |
| `lib/faculty-api.test.ts` | Updated tests | ~10 |
| `lib/admin-api.test.ts` | Updated tests | ~10 |
| `backend/tests/test_m1v2_prediction.py` | Updated 8 tests | ~30 |

---

## Appendix C: Decision Log

| Decision | Rationale | Reversible? |
|---|---|---|
| Return 200 + NO_DATA instead of 404 | Frontend can show clear message | Yes |
| Do NOT retrain on 80-student data | Insufficient features (11/25), insufficient labels | Yes |
| Do NOT modify M1 V2 artifact | Safety rule: artifact must not be modified | Yes |
| Accept NO_DATA as production state | Honest, correct, prevents false predictions | Yes |
| Do NOT populate features synthetically | Safety rule: no fabricated data | Yes |
