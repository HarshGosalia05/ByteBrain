# M2 v2 — Data Audit Report

**Audited:** 2026-09-01 (live read-only Supabase probe; read-only multi-table audit)
**Cohort:** CSE 6A — 1,200 students
**Scope:** M2 Next-Semester Performance Prediction (`semester_sgpa`, `semester_percentage` at T+1)
**Temporal contract:** Features from observation semester **T** only; target from semester **T+1**. No T+1 information may appear in `X`.

---

## 1. Data Sources Audited (Live Supabase, 6A)

| Table | 6A Rows | All Rows | Status | Used for M2 |
|---|---|---|---|---|
| `students` | 1,200 | 1,280 | ✅ | Yes (static bio + current_semester) |
| `student_semester_summary` | 9,600 | 10,100 | ✅ | **Primary source** (T features + T+1 targets) |
| `student_subject_performance` | 68,400 | 72,250 | ✅ | Yes (T-semester subject aggregates) |
| `student_subject_enrollment` | 68,400 | 72,250 | ✅ | Yes (T-semester registered subjects/credits) |
| `attendance_weekly` | 547,200 | 547,200 | ✅ | Yes (T-semester weekly attendance aggregates) |
| `student_learning_activity` | 547,200 | 547,200 | ✅ | Yes (T-semester engagement aggregates) |
| `student_lifestyle_survey` | 9,600 | 9,600 | ✅ | Yes (T-semester survey) |
| `student_skill_profile` | 19,200 | 19,200 | ✅ | Excluded (no semester anchor) |
| `career_preferences_v2` | 1,200 | 1,200 | ✅ | Excluded (not semester-valid) |
| `placement` | 1,200 | 1,200 | ✅ | Excluded (post-graduation → future leakage) |
| `subjects` | N/A | 99 | ✅ | Metadata reference |
| `faculty_student_map` | 1,280 | 1,280 | ✅ | Excluded (mentor assignment, not predictive) |
| `faculty` | N/A | 25 | ✅ | Metadata only |
| `departments` | N/A | 2 | ✅ | Metadata only |

---

## 2. Primary Source — `student_semester_summary` (Point-in-Time)

### Columns (live schema)
`semester_summary_id`, `student_id`, `enrollment_no`, `semester_no`, `academic_year`, `subjects_registered`, `credits_registered`, `credits_earned`, `semester_total_marks`, `semester_percentage`, `semester_sgpa`, `semester_grade`, `semester_attendance_percentage`, `backlog_count`, `semester_result`, `academic_standing`, `division`, `previous_sem_sgpa`, `sgpa_drift`, `sgpa_rolling_mean_3`, `previous_sem_backlog_count`, `backlog_change`, `cumulative_backlog_events`, `backlog_trajectory`, `attendance_aggregate_pct`, `is_m1_deployment_boundary`, `target_available_if_completed`.

**M2-relevant finding:** The table already carries a rich set of **pre-computed point-in-time temporal features** (only derived from current + prior semesters — no future info):
- `previous_sem_sgpa`, `previous_sem_backlog_count` — prior semester (T−1)
- `sgpa_drift` = SGPA(T) − previous_SGPA(T−1)
- `sgpa_rolling_mean_3` — trailing 3-semester SGPA mean
- `backlog_change`, `cumulative_backlog_events`, `backlog_trajectory` — backlog history
- `attendance_aggregate_pct` — attendance

These are valid T-time features (no T+1 leakage) and are the backbone of M2 point-in-time features.

### Live completeness (per semester, 6A) — all 1,200 × 8 = 9,600 rows, 100% complete

| Sem | n | sgpa n | pct n | backlog n |
|---|---|---|---|---|
| 1 | 1200 | 1200 | 1200 | 1200 |
| 2 | 1200 | 1200 | 1200 | 1200 |
| 3 | 1200 | 1200 | 1200 | 1200 |
| 4 | 1200 | 1200 | 1200 | 1200 |
| 5 | 1200 | 1200 | 1200 | 1200 |
| 6 | 1200 | 1200 | 1200 | 1200 |
| 7 | 1200 | 1200 | 1200 | 1200 |
| 8 | 1200 | 1200 | 1200 | 1200 |

No fabricated/placeholder rows for the 6A cohort — all summary rows are derived from real labeled performance.

### Target distribution: `semester_sgpa` / `semester_percentage` (6A)

| Sem | min_sgpa | max_sgpa | avg_sgpa | min_pct | max_pct | avg_pct | frac_zero_sgpa |
|---|---|---|---|---|---|---|---|
| 1 | 6.23 | 9.0 | 8.302 | 53.39 | 91.25 | 73.70 | 0 |
| 2 | 5.62 | 9.0 | 8.274 | 52.31 | 93.48 | 72.84 | 0 |
| 3 | 5.81 | 9.0 | 8.230 | 52.37 | 91.91 | 72.49 | 0 |
| 4 | 5.65 | 9.0 | 8.279 | 54.14 | 94.58 | 73.13 | 0 |
| 5 | 6.00 | 9.0 | 8.350 | 56.72 | 93.98 | 74.17 | 0 |
| 6 | 6.41 | 9.0 | 8.364 | 56.40 | 93.02 | 74.37 | 0 |
| 7 | 5.84 | 9.0 | 8.292 | 53.25 | 92.39 | 73.49 | 0 |
| 8 | **7.00** | **9.0** | **8.658** | 54.08 | 98.26 | **78.15** | 0 |

**Critical finding — Semester 8 is an internship/project term, not a normal academic semester:**
- `student_subject_enrollment` shows **1 subject** in semester 8 (all prior semesters have 7–9).
- Semester 8 SGPA is **compressed and higher**: min 7.0, avg 8.658, vs normal semesters (min 5.62–6.41, avg 8.23–8.36).
- Semester 8 percentage avg 78.15 vs normal 72.5–74.4.
- **Implication:** the T+1 target for observation T=7 is an internship term that is not distributionally comparable to the full academic semesters 2–7. Using it as a regression target would mix domains.

### Missingness (point-in-time)
- `sgpa_drift` is **NULL for semester 1** (no prior semester) — 0 non-null at sem 1, 1200 non-null sems 2–8. **Must be imputed.** Same logic applies to `previous_sem_sgpa`, `previous_sem_backlog_count`, `sgpa_rolling_mean_3` at semester 1.
- All target-critical columns (`semester_sgpa`, `semester_percentage`) are 0-null for every semester.

---

## 3. T → T+1 Transition Availability

| Observation T | Target T+1 | T+1 subjects | Domain |
|---|---|---|---|
| 1 | 2 | 8 | ✅ normal |
| 2 | 3 | 9 | ✅ normal |
| 3 | 4 | 8 | ✅ normal |
| 4 | 5 | 8 | ✅ normal |
| 5 | 6 | 8 | ✅ normal |
| 6 | **7** | 7 | ✅ normal (**temporal holdout**) |
| 7 | 8 | 1 | ⚠️ internship target (segmentarily non-comparable) |
| 8 | 9 | — | ❌ no next semester (final) |

Every one of the 1,200 students reaches all 8 semesters (`students_8 = 1200`, `min_sems = max_sems = 8`). No student has a missing intermediate semester.

---

## 4. Feature-Source Availability for Observation Semester T (point-in-time)

All feature sources carry T-semester-grainless data joinable to `(student_id, semester_no)`:

| Source | Rows/sem (6A) | Point-in-time valid at T | Notes |
|---|---|---|---|
| `attendance_weekly` | 7,200–8,600 enrollments ×8 wks | ✅ | weekly by enrollment; aggregate to T |
| `student_learning_activity` | 7,200–8,600 ×8 wk | ✅ | engagement volume/consistency |
| `student_subject_performance` | 9,600–10,800 | ✅ | marks by subject at T |
| `student_subject_enrollment` | 9,600–10,800 | ✅ | credits/subjects at T |
| `student_lifestyle_survey` | 1,200 | ✅ | one survey per student·semester |

---

## 5. Deployment Boundary (M2)

- All 1,200 students are currently at **semester 8** (final, internship). There is **no semester 9**.
- Therefore a **per-student forward prediction (`current T → T+1`) has no valid T+1 for the current cohort.**
- **Decision (non-fabricating):** M2 V2 exposes inference for any student with an eligible `T → T+1` (a T+1 that is a normal, existing academic semester). For the current cohort (at T=8, no T+1), the endpoint returns `NO_DATA` with reason `no upcoming academic semester`. This is honest and prevents fabricating a prediction where no future semester exists.
- The model, pipeline, artifact, backend API, and frontend are fully implemented and validated on historical transitions; they correctly serve any earlier-semester student/future cohort.

---

## 6. Training / Validation Domain (Decision)

| Item | Decision |
|---|---|
| Prediction unit | `(student_id, observation_semester T)` |
| Prediction horizon | one semester: T+1 |
| Targets | `semester_sgpa(T+1)`, `semester_percentage(T+1)` (two regression targets, matching legacy M2 contract) |
| Training transitions | T = 1..6 → target semester 2..7 (all full academic semesters) |
| Excluded transitions | T=7→8 (internship target, distributionally non-comparable); T=8 (no next semester) |
| Temporal holdout | **T=6 → predict semester 7** (newest normal transition; mirrors M1 V2 sem-7 holdout) |
| Group validation | GroupKFold by `student_id` (same student's transitions never split across train/test) |
| Leakage | T+1 outcome columns forbidden in `X`; T-only features |

---

## 7. Key Data Decisions for M2

### Feature sources (T-only)
1. **`student_semester_summary`** — primary: SGPA, %, marks, credits, backlogs, attendance, drift/rolling history.
2. **`student_subject_performance`** + **`student_subject_enrollment`** — T-semester subject-level aggregates (mean/σ of internal/mid/end marks, weighted, assignment/quiz).
3. **`attendance_weekly`** — T-semester aggregate attendance %.
4. **`student_learning_activity`** — T-semester engagement volume & consistency mean.
5. **`student_lifestyle_survey`** — T-semester stress/sleep/study-hour signals (numerically encoded).

### Tables NOT used for M2
| Table | Reason |
|---|---|
| `student_skill_profile` | No semester anchor; varies at student level not semester level |
| `career_preferences_v2` | Career intent, not next-semester academic performance |
| `placement` | Post-graduation outcome → future leakage by definition |
| `faculty_student_map` | Mentor assignment, not a predictive individual signal |
| `subjects` | Metadata already in enrollment |

---

## 8. Data Quality Summary

| Dimension | Rating | Notes |
|---|---|---|
| Completeness | EXCELLENT | 0 nulls in target columns; only expected sem-1 temporal-feature nulls |
| Consistency | EXCELLENT | No FK violations, no grain duplicates, all students reach 8 sems |
| Grain | CORRECT | `(student_id, semester_no)` unique per summary row |
| Coverage | COMPLETE | 1,200 students × 8 semesters, all transitions resolvable |
| Leakage risk | LOW (controllable) | Explicit T-only vs T+1 separation; sem-1 drift nulls only imputation item |
| Freshness | CURRENT | Loaded ETL from canonical 1200 6A cohort |

---

## 9. Impact on Later Phases
- Phase B (target): define SGPA+percentage at T+1; exclude sem-8 as target; deploy NO_DATA for current cohort.
- Phase D (features): build T-only feature set with sem-1 null imputation and subject-level aggregates.
- Phase E (leakage gate): fail-closed scan must confirm **no T+1 outcome column** enters `X`; reuse M1 V2 gate pattern but with **M2-specific forbidden list** (T+1 outcome cols), NOT M1's list.
- Phase G (validation): GroupKFold(student) + explicit temporal T=6→7 holdout; report both.
- Phase J (old vs new M2): compare against legacy `m2_next_semester_performance` artifact on its R² ~0.99 autocorrelation caveat.