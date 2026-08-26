# ML Feature Engineering Layer — Final Report

## 1. Existing ML Specifications Discovered

The project already specifies **4 ML models** with complete feature contracts:

| Model | Purpose | Algorithm | Grain |
|---|---|---|---|
| **M1** | Subject end-semester marks prediction | hist_gbm (selected) | (student_id, subject_id, semester_no) |
| **M2** | Next-semester SGPA/percentage prediction | hist_gbm (selected) | (student_id, semester_no) |
| **M3** | Next-semester at-risk binary classification | logistic regression (selected) | (student_id, semester_no) |
| **M4** | Career readiness scoring | Rule-based engine | (student_id) |

Existing code: `ml/src/m1-m4/` (config, data, train, evaluate), `ml/src/features.py` (inference features), `ml/tests/test_features.py` (40 tests).

## 2. Prediction Grain

| Model | Grain | Rows (live DB) |
|---|---|---|
| M1 | (student_id, subject_id, semester_no) | 3,850 |
| M2 | (student_id, semester_no) | 500 |
| M3 | (student_id, semester_no) | 500 |
| M4 | (student_id) | 80 |

## 3. Target Definition

| Model | Target | Type | Training rows | Deployment rows |
|---|---|---|---|---|
| M1 | `end_sem_marks` | Numeric (0-70) | 3,291 | 559 |
| M2 | `next_semester_percentage`, `next_semester_sgpa` | Numeric | 420 | 80 |
| M3 | `is_at_risk_next_sem` | Binary (0/1) | 420 | 80 |
| M4 | `placement_readiness_level` | Categorical (Low/Medium/High) | 80 | 0 |

M3 positive rate: 6.2% (26/420 at-risk students).

## 4. Feature Groups

### M1 (8 features)
- **Academic performance**: internal_marks, mid_sem_marks
- **Attendance**: attendance_percentage
- **Metadata**: subject_type, credits, semester_no, department_name, gender

### M2/M3 (11 features)
- **Semester history**: semester_no, subjects_registered, credits_registered, credits_earned, semester_total_marks, semester_percentage, semester_sgpa, semester_attendance_percentage, backlog_count
- **Metadata**: department_name, gender

### M4 (12 features)
- **Career preferences**: preferred_domain, dream_job_role, preferred_industry, preferred_work_mode, higher_studies_interest, entrepreneurship_interest, certification_interest, internship_completed
- **Academic aggregates**: avg_prior_percentage, avg_prior_sgpa, avg_prior_attendance, total_prior_backlogs

## 5. Final Feature List

### M1 Raw Features
1. internal_marks (numeric, 0-20)
2. mid_sem_marks (numeric, 0-50)
3. attendance_percentage (numeric, 0-100)
4. subject_type (categorical: Theory/Laboratory/Project/Internship)
5. credits (numeric, >0)
6. semester_no (numeric, 1-8)
7. department_name (categorical: CSE/BBA)
8. gender (binary: Male/Female -> is_male)

### M2/M3 Raw Features
1. semester_no (numeric, 1-8)
2. subjects_registered (numeric)
3. credits_registered (numeric)
4. credits_earned (numeric)
5. semester_total_marks (numeric)
6. semester_percentage (numeric, 0-100)
7. semester_sgpa (numeric, 0-10)
8. semester_attendance_percentage (numeric, 0-100)
9. backlog_count (numeric, >=0)
10. department_name (categorical)
11. gender (binary -> is_male)

### M4 Raw Features
1-8. Career preference fields (categorical/binary)
9-12. Academic aggregate fields (numeric)

## 6. Leakage Rules

| Rule | Affected Models | Detail |
|---|---|---|
| No target-derived features | M1 | Forbidden: total_marks, percentage, grade, grade_point, result_status, performance_category, ct1_marks, ct2_marks, attempt_number, latest_sgpa, overall_cgpa, overall_percentage, overall_attendance_percentage, total_backlogs, academic_standing |
| No future semester data | M2, M3 | Targets computed via shift(-1) within student; features only use current semester |
| No placement outcomes | M4 | Forbidden: target_package_lpa, placement_readiness_level |
| Grain uniqueness | All | No duplicate prediction rows per grain |
| Temporal separation | M2, M3 | Last semester per student = deployment (no target available) |

## 7. ML Dataset Schema

```
M1: student_id | subject_id | semester_no | internal_marks | mid_sem_marks | 
    attendance_percentage | subject_type | credits | department_name | gender | 
    end_sem_marks (target)

M2: student_id | semester_no | subjects_registered | credits_registered | 
    credits_earned | semester_total_marks | semester_percentage | semester_sgpa |
    semester_attendance_percentage | backlog_count | department_name | gender |
    next_semester_percentage (target) | next_semester_sgpa (target)

M3: student_id | semester_no | [same features as M2] |
    is_at_risk_next_sem (target: binary)

M4: student_id | preferred_domain | dream_job_role | preferred_industry |
    preferred_work_mode | higher_studies_interest | entrepreneurship_interest |
    certification_interest | internship_completed | avg_prior_percentage |
    avg_prior_sgpa | avg_prior_attendance | total_prior_backlogs |
    placement_readiness_level (target)
```

## 8. Files Created

| File | Description |
|---|---|
| `ml/src/feature_config.py` | Feature definitions, grain, leakage rules, null handling, forbidden features |
| `ml/src/feature_data.py` | Database-backed dataset builders for M1-M4 |
| `ml/tests/test_feature_engineering.py` | 54 unit tests (all pass) |
| `ml/verify_feature_engineering.py` | Live Supabase verification (24/24 checks pass) |

## 9. Files Modified

None. No existing files were modified.

## 10. Tests Added

54 tests in `ml/tests/test_feature_engineering.py`:
- Feature definition completeness (8 tests)
- Feature group coverage (3 tests)
- Target definitions (4 tests)
- M1 dataset builder (4 tests)
- M2 dataset builder (4 tests)
- M3 dataset builder (3 tests)
- M4 dataset builder (5 tests)
- Determinism (2 tests)
- Null handling (3 tests)
- Referential integrity (3 tests)
- No database writes (2 tests)
- Leakage prevention (6 tests)
- Training/deployment split (3 tests)
- Feature data types (3 tests)

## 11. Test Results

- **Feature engineering unit tests**: 54/54 pass
- **Analytics tests**: 41/41 pass (no regression)
- **Live verification**: 24/24 checks pass against live Supabase

## 12. Live Verification Results

| Check | Result | Detail |
|---|---|---|
| M1 total rows | PASS | 3,850 |
| M1 grain unique | PASS | 0 duplicates |
| M1 training rows | PASS | 3,291 |
| M1 deployment rows | PASS | 559 |
| M1 feature columns present | PASS | all present |
| M1 null checks (3) | PASS | 0 nulls in key features |
| M1 no forbidden columns | PASS | clean |
| M2 total rows | PASS | 500 |
| M2 grain unique | PASS | 0 duplicates |
| M2 training rows | PASS | 420 |
| M2 deployment rows | PASS | 80 |
| M2 target range | PASS | mean 63.97% |
| M3 total rows | PASS | 500 |
| M3 both classes | PASS | positive rate 6.2% |
| M4 total rows | PASS | 80 |
| M4 grain unique | PASS | 0 duplicates |
| M4 target classes | PASS | Medium=65, Low=15 |
| M4 aggregates (4) | PASS | 0 nulls |

## 13. Confirmation: ETL and Analytics Unchanged

- **ETL pipeline**: No files modified
- **Analytics repository**: No files modified
- **Analytics schemas**: No files modified
- **Analytics tests**: 41/41 still pass

## 14. Remaining Work for Actual ML Model

1. **Model training**: Run `ml/src/m1/train_m1.py`, `m2/train_m2.py`, `m3/train_m3.py`, `m4/build_m4.py`
2. **Model evaluation**: Evaluate metrics against acceptance criteria
3. **Prediction service**: Connect DB-backed features to existing inference pipeline
4. **API integration**: Wire up existing `predict.py` endpoints
5. **Dashboard**: Frontend ML insights pages (ML-09, ML-10, ML-11)
6. **Feedback loop**: Faculty feedback → M3 retraining

**STOP.** Feature engineering layer complete. No model training performed.
