# M1 v2 — Feature Contract

**Version:** 2.0
**Target:** `end_sem_marks` (integer [0, 70])
**Prediction point:** During semester T, after internal marks, mid-sem marks, weekly attendance (8 weeks), learning activity (8 weeks), and assignments/quizzes have been recorded — BEFORE the end-semester exam.

---

## 1. Feature Tiers

### Tier 1A: Current-Semester Pre-Exam Numeric Features

These features are available during semester T before the end-semester exam.

| Feature | Source Table | Column | Temporal Availability | Notes |
|---|---|---|---|---|
| `internal_marks` | `student_subject_performance` | `internal_marks` | Recorded mid-semester | 0–20; internal assessment |
| `mid_sem_marks` | `student_subject_performance` | `mid_sem_marks` | After mid-sem exam | 0–50 |
| `pre_endsem_assessment_pct` | `student_subject_performance` | `pre_endsem_assessment_pct` | After mid-sem exam | Composite (internal+mid)/70 × 100 |
| `assignment_score` | `student_subject_performance` | `assignment_score` | End of semester | 0–100 scale |
| `quiz_avg_marks` | `student_subject_performance` | `quiz_avg_marks` | End of semester | 0–100 |
| `submission_delay_days` | `student_subject_performance` | `submission_delay_days` | End of semester | Submission delay in days |

### Tier 1B: Attendance Aggregates (current semester)

| Feature | Source Table | Aggregation | Temporal Availability |
|---|---|---|---|
| `att_total_pct` | `attendance_weekly` | 100 × SUM(classes_attended) / SUM(classes_held) | After week 8 (pre-exam) |
| `att_rolling_4w_mean` | `attendance_weekly` | AVG(attendance_rolling_4w) across 8 weeks | After week 8 |
| `att_velocity_latest` | `attendance_weekly` | `attendance_velocity` of week 8 | After week 8 |

**Note:** `att_total_pct` uses ratio-of-sums (not mean-of-percentages) to avoid weighting bias from weeks with few classes held.

### Tier 1C: Learning Activity Aggregates (current semester)

| Feature | Source Table | Aggregation | Temporal Availability |
|---|---|---|---|
| `activity_volume_total` | `student_learning_activity` | SUM(activity_volume) across 8 weeks | After week 8 (pre-exam) |
| `avg_engagement_consistency` | `student_learning_activity` | AVG(engagement_consistency) across 8 weeks | After week 8 |
| `avg_assessment_completion_rate` | `student_learning_activity` | AVG(assessment_completion_rate) across 8 weeks | After week 8 |
| `avg_late_submission_rate` | `student_learning_activity` | AVG(late_submission_rate) across 8 weeks | After week 8 |

**Source note:** These are OULAD-inspired behavioral features adapted to CampusX data. No OULAD student IDs or labels were used or copied.

### Tier 1D: Subject and Student Metadata (stable)

| Feature | Source Table | Encoding | Temporal Availability |
|---|---|---|---|
| `credits` | `student_subject_enrollment` | numeric | At enrollment time |
| `semester_no` | `student_subject_performance` | numeric | At enrollment time |
| `subject_type` | `student_subject_enrollment` | OHE (Theory/Lab/Project/Internship) | At enrollment |
| `subject_domain` | `student_subject_performance` | OHE (Communication & General / Math & Statistics / Core CSE / etc.) | At enrollment |
| `is_male` | `students` | binary (1=Male, 0=Female) | At admission |
| `stress_ordinal` | `student_lifestyle_survey` | ordinal (Low=0/Medium=1/High=2) | At semester start |
| `study_hours_per_week` | `student_lifestyle_survey` | numeric | At semester start |

### Tier 2: Prior Semester Aggregates (from completed semesters < T)

These features capture longitudinal academic history. For semester 1, they are NaN (imputed with training median).

| Feature | Source Table | Aggregation | Temporal Availability |
|---|---|---|---|
| `prior_avg_sgpa` | `student_semester_summary` | MEAN(semester_sgpa) for sems < T | Available at start of sem T |
| `sgpa_drift_latest` | `student_semester_summary` | `sgpa_drift` at sem T-1 | Available at start of sem T |
| `prior_backlog_cumulative` | `student_semester_summary` | `cumulative_backlog_events` at sem T-1 | Available at start of sem T |
| `prior_avg_attendance` | `student_semester_summary` | MEAN(semester_attendance_percentage) for sems < T | Available at start of sem T |
| `prior_n_sems` | `student_semester_summary` | COUNT(completed sems < T) | Available at start of sem T |

---

## 2. Encoding Specification

### One-Hot Encoding (OHE)
- `subject_type` → `subtype_Theory`, `subtype_Laboratory`, `subtype_Project`, `subtype_Internship`
- `subject_domain` → `domain_Communication & General`, `domain_Math & Statistics`, `domain_Core CSE`, etc.
- Unknown/missing → `subtype_Unknown`, `domain_Unknown` (filled with 0 if not in training set)

### Ordinal Encoding
- `mental_stress_level` → `stress_ordinal`: Low=0, Medium=1, High=2
- Missing → NaN (imputed)

### Binary Encoding
- `gender` → `is_male`: Male=1, Female=0
- Missing → NaN (imputed)

---

## 3. FORBIDDEN Features

These columns MUST NEVER appear in the feature matrix X. They are:

### Target-Derived (direct leakage)
| Column | Reason |
|---|---|
| `end_sem_marks` | Target — removed from X |
| `total_marks` | = internal + mid_sem + end_sem → contains target |
| `percentage` | = (total_marks / 140) × 100 → contains target |
| `grade` | Derived from percentage → contains target |
| `grade_point` | Derived from grade → contains target |
| `result_status` | Pass/Fail derived from total_marks → contains target |
| `performance_category` | Derived category → contains target |
| `remarks` | Derived remark text → contains target |

### Student-Level Aggregates Including Current Semester
| Column | Reason |
|---|---|
| `latest_sgpa` | Includes current semester SGPA (target-era) |
| `overall_cgpa` | Includes all semesters including current |
| `overall_percentage` | Includes current semester outcome |
| `overall_attendance_percentage` | Snapshot including current |
| `total_backlogs` | Includes current semester backlogs |
| `academic_standing` | Derived from total performance |

### Post-Graduation (future leakage)
| Column | Reason |
|---|---|
| `placement_status` | Post-graduation outcome |
| `package_lpa` | Post-graduation salary |
| `package_tier` | Post-graduation tier |
| `placement_domain` | Post-graduation domain |
| `placement_date` | Future date |

### Semester-Level Outcome Columns
| Column | Reason |
|---|---|
| `semester_sgpa` | End-of-semester outcome |
| `semester_grade` | End-of-semester outcome |
| `semester_result` | End-of-semester outcome |
| `semester_percentage` | End-of-semester outcome |
| `credits_earned` | Determined by exam results |

---

## 4. Temporal Proof-of-Availability

| Feature | Available at Prediction Point? | Proof |
|---|---|---|
| `internal_marks` | ✅ YES | Recorded mid-semester, before end-exam |
| `mid_sem_marks` | ✅ YES | Mid-semester exam completed before end-exam |
| `pre_endsem_assessment_pct` | ✅ YES | Composite of internal+mid; no end-sem used |
| `assignment_score` | ✅ YES | All assignments scored before end-exam |
| `quiz_avg_marks` | ✅ YES | All quizzes before end-exam |
| `att_total_pct` | ✅ YES | Week 8 complete before exam |
| `activity_volume_total` | ✅ YES | Week 8 complete before exam |
| `prior_avg_sgpa` | ✅ YES | From completed semesters < T |
| `study_hours_per_week` | ✅ YES | Survey captured at semester start |
| `subject_type` | ✅ YES | Known at enrollment |
| `credits` | ✅ YES | Known at enrollment |
| `gender` | ✅ YES | Student profile attribute |

---

## 5. Feature Schema Version

**Schema version:** `v2.0`
**Serialized in:** artifact metadata field `feature_schema_version`
**Column list:** stored in `artifact["feature_names"]`

Any inference call MUST use `X.reindex(columns=artifact["feature_names"], fill_value=0)` to align OHE columns correctly.

---

## 6. Imputation Policy

Missing values are handled as follows during training:
- Strategy: median imputation (fit on training fold only — never on validation)
- All Tier 2 features for semester 1 students are NaN (no prior history) → imputed
- OHE columns for unseen categories → filled with 0 (reindex)

During inference:
- Same preprocessor object (serialized in artifact) transforms input features
- Missing student data → predictor returns `readiness_status: NO_DATA`
