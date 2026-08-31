# M1 v2 — Data Audit Report

**Audited:** 2026-08-31 (live Supabase probe)
**Cohort:** CSE 6A — 1,200 students
**Scope:** M1 Subject Performance Prediction (end_sem_marks)

---

## 1. Data Sources Audited (Live Supabase)

| Table | 6A Rows | All Rows | Status |
|---|---|---|---|
| `students` | 1,200 | 1,280 | ✅ |
| `student_subject_enrollment` | 68,400 | 72,250 | ✅ |
| `student_subject_performance` | 68,400 | 72,250 | ✅ |
| `attendance_weekly` | 547,200 | 547,200 | ✅ |
| `student_learning_activity` | 547,200 | 547,200 | ✅ |
| `student_semester_summary` | 9,600 | 10,100 | ✅ |
| `student_lifestyle_survey` | 9,600 | 9,600 | ✅ |
| `student_skill_profile` | 19,200 | 19,200 | ✅ (excluded from M1) |
| `career_preferences_v2` | 1,200 | 1,200 | ✅ (excluded from M1) |
| `placement` | 1,200 | 1,200 | ✅ (excluded — future leakage) |
| `subjects` | N/A | 99 | ✅ |

---

## 2. 6A Cohort Verification

| Check | Result |
|---|---|
| Total 6A students | 1,200 |
| Student ID format | `STU6A0001` … `STU6A1200` |
| Department | CSE (all students) |
| Division | 6A |
| Current semester | 8 (all 1,200 students) |
| Performance rows per student | 57 (average, sems 1–8) |

---

## 3. Performance Table Analysis

### Semester Distribution

| Semester | Performance Rows | Labeled (end_sem NOT NULL) |
|---|---|---|
| 1 | 9,600 | 9,600 (100%) |
| 2 | 9,600 | 9,600 (100%) |
| 3 | 10,800 | 10,800 (100%) |
| 4 | 9,600 | 9,600 (100%) |
| 5 | 9,600 | 9,600 (100%) |
| 6 | 9,600 | 9,600 (100%) |
| 7 | 8,400 | 8,400 (100%) |
| 8 | 1,200 | 1,200 (100%) |

**Total:** 68,400 rows, ALL fully labeled (no missing `end_sem_marks`).

### Subject Count per Semester

| Semester | Subjects |
|---|---|
| 1 | 8 |
| 2 | 8 |
| 3 | 9 |
| 4 | 8 |
| 5 | 8 |
| 6 | 8 |
| 7 | 7 |
| 8 | 1 |

Note: Semester 3 has 9 subjects (explaining 10,800 vs 9,600 rows for other semesters).

### Marks Ranges

| Column | Min | Max | Nulls |
|---|---|---|---|
| `internal_marks` | 2 | 20 | 0 |
| `mid_sem_marks` | 1 | 50 | 0 |
| `end_sem_marks` | 2 | 70 | 0 |
| `assignment_score` | 0.0 | 93.07 | 0 |
| `quiz_avg_marks` | 0.0 | 97.4 | 0 |
| `submission_delay_days` | 0.0 | — | 0 |
| `pre_endsem_assessment_pct` | 11.8 | 95.49 | 0 |

### Target Distribution by Internal Marks Band

| Internal Band | n | Mean end_sem_marks |
|---|---|---|
| 0–10 | 843 | 39.84 |
| 11–14 | 7,642 | 46.67 |
| 15–16 | 10,639 | 48.71 |
| 17–18 | 14,529 | 50.40 |
| 19–20 | 34,747 | 55.03 |

**Finding:** Strong monotonic signal — internal marks are a reliable predictor of end_sem performance.

---

## 4. Attendance Weekly Analysis

| Metric | Value |
|---|---|
| Total rows | 547,200 |
| Weeks per enrollment | 8 (all semesters, all subjects) |
| Week range | 1–8 |
| Null `week_number` | 0 |
| Null `classes_held` | 0 |

Each enrollment record has exactly 8 weekly attendance entries. Aggregating across weeks gives a clean point-in-time attendance signal.

---

## 5. Learning Activity Analysis

| Metric | Value |
|---|---|
| Total rows | 547,200 |
| Weeks per enrollment | 8 |
| `activity_mapping_note` | "OULAD-inspired behavioral features; no OULAD rows/IDs copied" |
| Null `activity_volume` | 0 |
| `engagement_consistency` range | 0.0–1.0 |

---

## 6. Lifestyle Survey Analysis

| Metric | Value |
|---|---|
| Total rows | 9,600 (6A) |
| Surveys per student | 8 (semesters 1–8) |
| Nulls in survey columns | None observed |
| Stress levels | Low / Medium / High |

---

## 7. Semester Summary Analysis

### Deployment Boundary
- `is_m1_deployment_boundary = TRUE` for **semester 7** (1,200 rows)
- `is_m1_deployment_boundary = FALSE` for all other semesters
- **Interpretation:** Semester 7 is designated as the model deployment/prediction point

### `target_available_if_completed`
- All 9,600 rows have `target_available_if_completed = TRUE`
- This means end_sem_marks are available for all semesters (training can use any)

---

## 8. FK Integrity

| Check | Result |
|---|---|
| Orphan performance rows (no matching enrollment) | 0 |
| Orphan attendance rows (no matching enrollment) | 0 |
| All 6A students have enrollment records | ✅ |

---

## 9. Key Data Decisions for M1

### Training/Validation Split

**Design decision:** Use semesters 1–6 as training, semester 7 as temporal holdout.

Rationale:
- `is_m1_deployment_boundary=TRUE` marks semester 7 as the production prediction point
- Students are currently in semester 8 — semester 7 is their most recent completed semester
- Semesters 1–6 provide rich longitudinal training data (57,600 rows)
- Semester 7 provides a genuine future-semester holdout (8,400 rows)
- Semester 8 has only 1 subject (internship/project) — too sparse for M1 evaluation

### Tables NOT Used for M1

| Table | Reason Excluded |
|---|---|
| `student_skill_profile` | No temporal anchor; doesn't vary at subject-semester level |
| `career_preferences_v2` | Career intent doesn't predict within-semester exam marks |
| `placement` | Post-graduation outcome; future leakage by definition |
| `subjects` | Metadata already in enrollment table; redundant |
| `faculty_student_map` | Faculty assignment → not individual predictive signal |

---

## 10. Data Quality Summary

| Dimension | Rating | Notes |
|---|---|---|
| Completeness | EXCELLENT | 0 nulls in all key columns |
| Consistency | EXCELLENT | No FK violations, no grain duplicates |
| Grain | CORRECT | (student, subject, semester) is unique |
| Coverage | COMPLETE | All 1,200 students × all 8 semesters × all subjects |
| Leakage risk | LOW | Clear separation between pre-exam features and exam outcome |
| Data freshness | CURRENT | Loaded via ETL from canonical 1200-student 6A cohort |
