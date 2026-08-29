# KenexAI KDAC-3 — Forensic Audit Report
**Audit Date:** 2026-08-29  
**Auditor:** Antigravity (read-only investigation, no modifications made)  
**Scope:** CSE Semester 7 (live); BBA Semester 5 excluded per instructions  
**Connection:** Supabase pooler `aws-1-ap-south-1.pooler.supabase.com:6543`, session set to `default_transaction_read_only=on`

---

## Section 1 — Table Inventory (Task A)

All public BASE TABLE rows with live counts as of audit time.

| Table | Row Count |
|---|---|
| `attendance` | 3,850 |
| `attendance_change_log` | 104 |
| `career_preferences` | 80 |
| `daily_attendance_07` | 6,250 |
| `departments` | 2 |
| `faculty` | 25 |
| `faculty_student_map` | 80 |
| `lifestyle_survey` | 80 |
| `ml_predictions` | **5,072** |
| `performance_change_log` | 33 |
| `prediction_feedback` | 35 |
| `risk_predictions` | 80 |
| `student_goals` | 1 |
| `student_messages` | 0 |
| `student_semester_summary` | 500 |
| `student_subject_enrollment` | 3,850 |
| `student_subject_performance` | 3,850 |
| `students` | 80 |
| `subjects` | 99 |
| `users` | 106 |
| `weekly_timetable_07` | 15 |

**Total tables:** 21  
**Database functions:** 1 (`trg_calculate_performance`, type `FUNCTION`)  
**Database triggers:** 1 named `trigger_update_performance` on `student_subject_performance`, fires on both INSERT and UPDATE, action timing BEFORE.

---

## Section 2 — Database Trigger Analysis

### `trigger_update_performance` -> `trg_calculate_performance`

The trigger fires **BEFORE INSERT or UPDATE** on `student_subject_performance`. Based on `migrations/17_fix_marks_derivation_trigger.sql`, it enforces a **Strict Completeness Rule**:

> Derived fields (`total_marks`, `percentage`, `grade`, `result_status`, `performance_category`) are computed **ONLY IF** all three of {`internal_marks`, `mid_sem_marks`, `end_sem_marks`} are non-NULL. If any are NULL, all derived fields are set to NULL.

**Consequence for CSE Sem 7:** Since `end_sem_marks` is NULL for every Sem 7 row, the trigger will never compute derived fields. The `total_marks`, `percentage`, `grade`, `result_status`, and `performance_category` columns stay NULL for all 350 live Sem 7 subject-performance rows.

---

## Section 3 — CSE Sem 7 Subject Performance State

### 3.1 Live `student_subject_performance` (Sem 7)

Queried 200 rows across 28+ students, all subjects SUB0050-SUB0056.

**Universal finding — every CSE Sem 7 row has this pattern:**

| Field | Live Value |
|---|---|
| `internal_marks` | Non-NULL integer (entered by faculty) |
| `mid_sem_marks` | Non-NULL integer (entered by faculty) |
| `end_sem_marks` | **NULL** (not yet entered) |
| `total_marks` | **NULL** (trigger blocked — completeness rule) |
| `percentage` | **NULL** |
| `grade` | **NULL** |
| `result_status` | **NULL** |
| `performance_category` | **NULL** |

**Representative rows (STU000001, Sem 7):**

| subject_id | internal | mid_sem | end_sem | total | grade | result |
|---|---|---|---|---|---|---|
| SUB0050 | 8 | 36 | NULL | NULL | NULL | NULL |
| SUB0051 | 13 | 39 | NULL | NULL | NULL | NULL |
| SUB0052 | 16 | 34 | NULL | NULL | NULL | NULL |
| SUB0053 | 14 | 40 | NULL | NULL | NULL | NULL |
| SUB0054 | 14 | 32 | NULL | NULL | NULL | NULL |
| SUB0055 | 15 | 39 | NULL | NULL | NULL | NULL |
| SUB0056 | 14 | 37 | NULL | NULL | NULL | NULL |

The trigger is working correctly. The C1 (internal) and C2 (mid-sem) values ARE populated for all 50 CSE students across all Sem 7 subjects. End-sem exams have not yet been conducted.

---

## Section 4 — student_semester_summary Contradiction (Task B / Task E)

### 4.1 Live Query Results

Queried all 50 CSE student rows for `semester_no = 7`.

**ALL 50 Sem 7 summary rows exhibit the following contradiction:**

| Field | Expected (sem pending) | Actual Live Value |
|---|---|---|
| `semester_total_marks` | 0 or NULL | **0** |
| `semester_percentage` | NULL | **0.0** |
| `semester_sgpa` | NULL | **0.0** |
| `semester_grade` | NULL | **"B"** |
| `semester_result` | NULL | **"PASS"** |
| `backlog_count` | 0 or NULL | **0** |
| `credits_registered` | valid | **19** |
| `credits_earned` | should be 0 or NULL | **19** |

**Statistical summary:**

```
Total Sem 7 rows for CSE: 50
With semester_total_marks=0 AND semester_sgpa=0.0: 50 (100%)
With semester_grade IS NOT NULL while above: 50 (100%)
With semester_result = 'PASS' while above: 50 (100%)
```

This is a **universal stale-data contradiction** across all 50 students:
- Marks are zero (no end-sem marks available, trigger cannot compute)
- SGPA is 0.0
- Yet grade = "B" and result = "PASS" and credits_earned = 19

The `student_semester_summary` Sem 7 rows were pre-populated with placeholder grades/results at seed time and have **not been updated** by the trigger system. The trigger on `student_subject_performance` does not cascade updates into `student_semester_summary`.

---

## Section 5 — students.latest_sgpa vs Summary Data (Task B)

### 5.1 What `latest_sgpa` contains

50 CSE students have non-zero `latest_sgpa` values populated via migration seed (`03_students_data.sql`), representing Sem 6 (completed) SGPA values. Range: 2.89 (STU000032) to 10.0 (STU000002, STU000009, etc.)

### 5.2 Cross-check vs student_semester_summary

For all 50 CSE students:
- `student_semester_summary.semester_sgpa` for Sem 7 = **0.0** (100%)
- `students.latest_sgpa` has a non-zero value drawn from Sem 6

**33 out of 50 students** have a `latest_sgpa` that does **NOT match** their Sem 6 `student_semester_summary` SGPA. The two values are maintained independently with no automatic reconciliation.

**Sample divergence (latest_sgpa vs sem6_sgpa from summary):**

| student_id | students.latest_sgpa | sem6_sgpa | delta |
|---|---|---|---|
| STU000001 | 7.84 | 7.77 | +0.07 |
| STU000003 | 7.89 | 8.09 | -0.20 |
| STU000025 | 7.53 | 8.14 | **-0.61** |
| STU000032 | 2.89 | 3.64 | **-0.75** |
| STU000041 | 3.42 | 4.32 | **-0.90** |
| STU000050 | 7.84 | 7.50 | +0.34 |

The delta for STU000032 and STU000041 is particularly large — `students.latest_sgpa` appears to reflect a different computation or different semester than `student_semester_summary.semester_sgpa` for Sem 6.

### 5.3 ml_predictions (type=m2) vs students.latest_sgpa

The M2 model predicts `predicted_next_semester_sgpa`. Sample M2 predictions for STU000001:

| semester_no (input) | predicted_next_sgpa | actual students.latest_sgpa |
|---|---|---|
| 1 | 6.25 | 7.84 |
| 2 | 6.17 | 7.84 |
| 3 | 6.09 | 7.84 |
| 6 | 6.21 | 7.84 |
| 7 | 6.25 | 7.84 |

**Zero matches** between M2 `predicted_next_semester_sgpa` and `students.latest_sgpa`. M2 predictions are **not written back** to `students.latest_sgpa`; it is a static denormalized field from the seed migration.

---

## Section 6 — risk_predictions Table Anomalies

### 6.1 Schema Discovery

| column | type |
|---|---|
| `risk_prediction_id` | varchar |
| `student_id` | varchar |
| `enrollment_no` | bigint |
| `prediction_status` | varchar |
| `prediction_timestamp` | **double precision** (Unix timestamp as float) |
| `created_at` | timestamp without time zone |
| `updated_at` | timestamp without time zone |

`prediction_timestamp` is stored as `double precision` (Unix epoch float), not a `timestamptz`. Sample value: `1784922204.15426`.

### 6.2 Status Distribution (CSE, first 20 rows)

| prediction_status | count |
|---|---|
| LOW | 4 |
| MODERATE | 12 |
| CRITICAL | 4 |

All 80 rows were seeded with `prediction_status = 'Pending'`. Subsequently updated. Only STU000001 has `updated_at != created_at` (updated 2026-07-24); the remaining 79 have `updated_at = created_at = '2026-07-20'`.

---

## Section 7 — ml_predictions Distribution

### 7.1 Row Counts by Model Type (CSE cohort, first 200 rows)

| prediction_type | rows in sample |
|---|---|
| m1 | 170 |
| m2 | 14 |
| m3 | 14 |
| m4 | 2 |

Total `ml_predictions` in the database: **5,072 rows** (all students, all types).

### 7.2 M1 Predictions

Predict `predicted_end_sem_marks` per subject per semester. Sample: STU000001, SUB0001, Sem 1 = 51.5; SUB0004 = 49.9. Generated 2026-08-13, model version "1".

### 7.3 M2 Predictions

Predict `predicted_next_semester_sgpa` and `predicted_next_semester_percentage`. One row per completed semester (Sem 1-7 for STU000001). Sample: STU000001 Sem 7 = SGPA 6.25, percentage 57.51.

M2 predictions for Sem 7 are forward-looking estimates using Sem 6 data. Sem 7 SGPA is not yet derivable (end-sem pending).

### 7.4 M3 Predictions

Predict `is_at_risk_next_sem` (binary 0/1). Sample: STU000001, all semesters 1-7, `is_at_risk_next_sem = 0`.

### 7.5 M4 Predictions

Predict `career_readiness_score` and `career_readiness_level`. Sample: STU000001, score 54.39, level "Medium".

**Duplicates observed:** 2 rows for STU000001 with identical values (expected — append-only schema). Latest must be resolved via `generated_at DESC` at read time.

---

## Section 8 — Outlier Students (Task E)

### Live values for STU000032 and STU000041

| student_id | total_backlogs | latest_sgpa | overall_cgpa | credits_reg | credits_earned | standing |
|---|---|---|---|---|---|---|
| STU000032 (Jiya Patel) | **24** | 2.89 | 2.86 | 159 | 91 | Needs Improvement |
| STU000041 (Yash Trivedi) | **25** | 3.42 | 2.80 | 159 | 88 | Needs Improvement |

These are the two highest backlog counts in the cohort. Credits earned (91 and 88) are significantly below 159 registered, consistent with 24-25 backlogs. Values match the seed migration data — these are genuinely low-performing students, not data errors.

Both have `student_semester_summary` Sem 7 showing grade "B", result "PASS" — same universal stale-data contradiction as all 50 students.

**SGPA divergences are the largest in the dataset:**
- STU000032: `students.latest_sgpa = 2.89` vs `sem6_sgpa = 3.64` — delta **-0.75**
- STU000041: `students.latest_sgpa = 3.42` vs `sem6_sgpa = 4.32` — delta **-0.90**

---

## Section 9 — prediction_feedback Table

- **Row count:** 35
- **Sample:** All 10 most recent rows have `feedback_action = "confirmed"` with identical note: "Student is currently progressing well; confirmed on track with no next-sem risk."
- All feedback references `model_version = null`
- Two faculty IDs involved: FAC013 and FAC015
- All generated at `2026-08-14 08:30:28-30` UTC (2-second window)

The bulk-identical confirmation notes and narrow 2-second batch window strongly indicates this was an automated or scripted batch operation, not genuine manual faculty review.

---

## Section 10 — Pipeline Correctness Assessment

| Model | Status | Key Finding |
|---|---|---|
| M1 | Active (5072 total rows) | Predictions exist for Sem 1-6 subjects; Sem 7 subjects (SUB0050-56) not in first 200 rows |
| M2 | Active | Predictions exist per semester; never written back to `students.latest_sgpa` |
| M3 | Active | Binary at-risk per semester; not reconciled with `risk_predictions` table |
| M4 | Active | Career readiness; duplicate rows per student (by design, latest resolved by `generated_at DESC`) |

**Critical gap:** `risk_predictions` (legacy table, schema: varchar status, float timestamp) and `ml_predictions` M3 rows (is_at_risk_next_sem binary) represent the same concept — next-semester risk — but are completely separate tables with no join path or reconciliation logic.

---

## Section 11 — Summary of Findings (Ranked by Severity)

| # | Finding | Severity | Affected |
|---|---|---|---|
| F-01 | `student_semester_summary` Sem 7: ALL 50 rows have marks=0, sgpa=0.0, yet grade='B' and result='PASS' — stale placeholder data inconsistent with in-progress state | **CRITICAL** | 50 students |
| F-02 | `student_subject_performance` Sem 7: `end_sem_marks` NULL for all 350 rows; trigger correctly blocks derivation but `student_semester_summary` is never cascaded | HIGH | 350 rows |
| F-03 | `students.latest_sgpa` does not match `student_semester_summary.sem6_sgpa` for 33 of 50 students; independently maintained with no reconciliation | HIGH | 33 of 50 students |
| F-04 | M2 predictions are never written back to `students.latest_sgpa`; the field is a static seed artifact, not updated by the ML pipeline | HIGH | All students |
| F-05 | STU000032 and STU000041 have largest `latest_sgpa` vs Sem 6 SGPA divergence (-0.75 and -0.90 respectively) | MEDIUM | 2 students |
| F-06 | `risk_predictions.prediction_timestamp` stored as `double precision` float (Unix epoch) instead of `timestamptz` | MEDIUM | All 80 rows |
| F-07 | `risk_predictions` and `ml_predictions` M3 are separate and unreconciled despite representing the same risk concept | MEDIUM | All students |
| F-08 | `prediction_feedback` 35 rows with bulk-identical notes in a 2-second window — not genuine manual faculty review | LOW | 35 rows |
| F-09 | M4 predictions have duplicate rows per student (append-only by design; latest must be enforced at read time) | LOW | All students |
| F-10 | `student_messages` table has 0 rows — messaging feature not active | INFO | — |

---

## Section 12 — Read-Only Compliance Statement

- No INSERT, UPDATE, DELETE, ALTER, or DDL was executed
- Connection established with `options="-c default_transaction_read_only=on"`
- No source code, config, migration, or any database row was modified
- `performance_change_log` has 33 rows (pre-existing); no rows were added
- This file (`plan_25_08/analysis_database.md`) is the sole output artifact of the audit
