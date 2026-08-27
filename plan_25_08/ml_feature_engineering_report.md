# ML Feature Engineering Report — V1

## 1. ML Use Case

**Next-Semester Risk Prediction (M3)**

For each student-semester N: given completed semester N features, predict whether semester N+1 will be at-risk (FAIL/ATKT or new backlogs).

This is a rolling prediction pattern, not semester-7-specific. The model generalizes across all semesters.

## 2. Prediction Target

| Property | Value |
|----------|-------|
| Target column | `is_at_risk_next_sem` |
| Data type | Binary (0 = safe, 1 = at-risk) |
| Construction | `(next_result IN ('FAIL','ATKT')) OR (next_backlogs > 0)` |
| Source columns | `student_semester_summary.semester_result`, `student_semester_summary.backlog_count` |
| Derivation | `shift(-1)` within `groupby("student_id")` |
| Positive rate (live) | 3.33% (10/300 training rows) |

## 3. Feature Definitions

### 3.1 Selected Features (11)

| # | Feature | Source Table | Source Column | Type | Availability |
|---|---------|-------------|---------------|------|-------------|
| 1 | `semester_no` | `student_semester_summary` | `semester_no` | Numeric | END_OF_SEMESTER |
| 2 | `subjects_registered` | `student_semester_summary` | `subjects_registered` | Numeric | END_OF_SEMESTER |
| 3 | `credits_registered` | `student_semester_summary` | `credits_registered` | Numeric | END_OF_SEMESTER |
| 4 | `credits_earned` | `student_semester_summary` | `credits_earned` | Numeric | END_OF_SEMESTER |
| 5 | `semester_total_marks` | `student_semester_summary` | `semester_total_marks` | Numeric | END_OF_SEMESTER |
| 6 | `semester_percentage` | `student_semester_summary` | `semester_percentage` | Numeric | END_OF_SEMESTER |
| 7 | `semester_sgpa` | `student_semester_summary` | `semester_sgpa` | Numeric | END_OF_SEMESTER |
| 8 | `semester_attendance_percentage` | `student_semester_summary` | `semester_attendance_percentage` | Numeric | END_OF_SEMESTER |
| 9 | `backlog_count` | `student_semester_summary` | `backlog_count` | Numeric | END_OF_SEMESTER |
| 10 | `department_name` | `students` | `department_name` | Categorical | END_OF_SEMESTER |
| 11 | `gender` | `students` | `gender` | Binary | END_OF_SEMESTER |

All features are direct column reads with no aggregation needed.

### 3.2 Feature Sources

| Source Table | Grain | Used For | Row Count |
|-------------|-------|----------|-----------|
| `student_semester_summary` | (student_id, semester_no) | 9 numeric features + target derivation | 500 |
| `students` | student_id | department_name, gender (2 features) | 80 |

### 3.3 Excluded Feature Sources

| Source | Reason Excluded |
|--------|----------------|
| `student_subject_performance` | Different grain (student-subject-semester). Used by M1 only. |
| `attendance` | M2/M3 uses `semester_attendance_percentage` from `student_semester_summary` instead. |
| `lifestyle_survey` | Used by M4 only (career readiness). Not part of M2/M3 design. |
| `career_preferences` | Used by M4 only. Career intent data, not relevant to academic risk. |
| `daily_attendance_07` | Semester 7 only — no training equivalent. |

### 3.4 Explicitly Excluded Columns (Leakage)

| Column | Reason |
|--------|--------|
| `semester_result` | Target-derived (shifted to create target) |
| `latest_sgpa`, `overall_cgpa`, `overall_percentage`, `overall_attendance_percentage`, `total_backlogs`, `academic_standing` | Cumulative student-level (includes future semester data) |
| `total_marks`, `percentage`, `grade`, `grade_point`, `result_status`, `performance_category`, `ct1_marks`, `ct2_marks` | Subject-level performance (different grain) |
| `end_sem_marks`, `internal_marks`, `mid_sem_marks` | M1-specific features |

## 4. Feature Grain

**One row = one student at one completed semester.**

- Training rows: student-semester pairs where the NEXT semester's data exists
- Deployment rows: student-semester pairs where the NEXT semester's data does NOT exist

## 5. Temporal Boundary

```
Features:     Available AFTER semester N completes (SGPA, total marks, backlog_count, etc.)
Target:       Derived from semester N+1 data (shifted forward by 1 semester)
Leakage rule: NO semester N+1 information may appear in semester N features
```

### Example

For a semester-6 training row predicting semester-7 risk:

| Allowed (features from sem 6) | Forbidden (from sem 7+) |
|-------------------------------|------------------------|
| semester_sgpa = 8.2 | semester_sgpa of sem 7 |
| backlog_count = 1 | backlog_count of sem 7 |
| semester_attendance_percentage = 85 | semester_result of sem 7 |

## 6. Leakage Prevention Rules

1. **No future semester data**: Features from semester N must NOT contain any information from semester N+1 or later.
2. **No cumulative student-level features**: `latest_sgpa`, `overall_cgpa`, etc. are forbidden — they include future semester data.
3. **No target-derived columns**: `semester_result` is used to compute the target but must not appear as a feature.
4. **No subject-level data**: `student_subject_performance` columns are at a different grain.
5. **Temporal split**: The last semester per student is ALWAYS deployment (no target available).
6. **No data augmentation**: Feature values come from the actual database state.

## 7. Training/Deployment Split

| Split | Definition | Row Count (Live) |
|-------|-----------|-----------------|
| Training | semesters where shift(-1) produced NOT NULL values | 300 |
| Deployment | last semester per student (no next-semester data) | 50 |

## 8. Missing-Value Strategy

- **Null values in features**: Preserved as-is. No imputation at feature-engineering time.
- **Missing optional data sources**: Students without certain data get NULL for those features.
- **Threshold**: Features with >5% nulls trigger a validation warning.
- **Live result**: 0% nulls across all 11 features (complete data for V1 scope).

## 9. Feature Storage

Features are generated on demand from PostgreSQL. No persistent feature table is created. The same query + same config = same output.

## 10. Reproducibility Strategy

- Same DB state + same V1Config = same feature values
- No random behavior in feature engineering
- Deterministic SQL queries with fixed ORDER BY
- Target construction uses pandas shift(-1) which is deterministic

## 11. Validation Rules

34 validation checks implemented:

| Category | Checks |
|----------|--------|
| Student IDs | All 50 expected IDs present |
| Grain | No duplicate (student_id, semester_no) rows |
| Row counts | Expected 350 total, 300 training, 50 deployment |
| Numeric ranges | All 9 numeric features within valid bounds |
| Categorical | Gender ∈ {Male, Female}, department ∈ {CSE} |
| Nulls | All features ≤5% nulls |
| Leakage | No forbidden columns in feature set |
| Temporal | Training semesters = [1-6], deployment = [7] |
| Target | Binary values, non-degenerate distribution |
| Referential | All rows have department_name (JOIN succeeded) |
| Determinism | Metadata consistent across runs |

## 12. Test Results

### Unit Tests: 55/55 PASSED

| Test Category | Count |
|--------------|-------|
| Configuration | 14 |
| Feature Correctness | 5 |
| Join Correctness | 3 |
| Missing Data | 3 |
| Leakage Prevention | 6 |
| Grain Integrity | 3 |
| Determinism | 2 |
| Scope Filtering | 3 |
| Training/Deployment Split | 4 |
| Target Construction | 2 |
| Validation | 3 |
| No DB Writes | 1 |
| Feature Data Types | 3 |
| Config Container | 2 |

### Existing ML Tests: 54/54 PASSED

No regressions in existing feature engineering tests.

### Live Verification: 34/34 CHECKS PASSED

```
Students:              50 (STU000001-STU000050)
Total rows:            350
Training rows:         300
Deployment rows:       50
Feature columns:       11
Positive rate:         3.33% (10 at-risk)
Build time:            0.26s
Validation time:       0.00s
```

## Files Changed

| Action | File | Lines |
|--------|------|-------|
| NEW | `ml/src/features/__init__.py` | 18 |
| NEW | `ml/src/features/v1_config.py` | 211 |
| NEW | `ml/src/features/v1_dataset.py` | 171 |
| NEW | `ml/src/features/v1_validation.py` | 210 |
| NEW | `ml/tests/test_v1_feature_engineering.py` | 550 |
| NEW | `ml/verify_v1_dataset.py` | 201 |

**Total: 6 new files, 0 modified files.**

## Scope Constraints

- Department: CSE
- Students: STU000001–STU000050
- Semesters: 1–6 (training), 7 (deployment)
- Academic year: 2026-27
- No models trained
- No predictions generated
- No ETL modifications
- No API changes
- No dashboard changes
