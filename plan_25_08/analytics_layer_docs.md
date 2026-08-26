# Analytics Data/Query Layer — Documentation

## Purpose

Read-only, deterministic, rule-based analytics layer that reads from ETL-produced PostgreSQL tables and computes answers for four query categories. **No ML, no GenAI, no dashboard UI, no authentication, no deployment.**

The layer is a single repository class (`AnalyticsRepository`) exposing 14 query methods across four categories (A–D). All methods are async, parameterized, and return Pydantic response models.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  FastAPI / API routers (not implemented in V1)       │
├──────────────────────────────────────────────────────┤
│  AnalyticsRepository  (analytics_repo.py)            │
│  ─ 14 read-only query methods                        │
│  ─ accepts asyncpg.Pool, returns Pydantic models     │
│  ─ $N positional params, $N::int/$N::bigint casts    │
├──────────────────────────────────────────────────────┤
│  Supabase PostgreSQL (PgBouncer pooler)              │
│  21 public tables | ETL-produced, frozen             │
└──────────────────────────────────────────────────────┘
```

---

## Tables Read

| Table | Read by Category | Grain |
|---|---|---|
| `students` | A, D | One row per student |
| `subjects` | B, C, D | One row per subject |
| `student_subject_performance` | A, B, C | One row per student-subject |
| `student_semester_summary` | A, D | One row per student-semester |
| `attendance_summary` | A, B, C | One row per student-semester-subject |
| `student_subject_enrollment` | A | One row per student-subject enrollment |
| `departments` | C | One row per department |

---

## Query Categories

### A. Student Analytics (4 methods)

| Method | Grain | Source Tables |
|---|---|---|
| `get_student_academic_profile(student_id)` | Single student | students, student_semester_summary, student_subject_enrollment |
| `get_student_semester_history(student_id, ...)` | Semester-semester trend | student_semester_summary |
| `get_student_attendance_summary(student_id, ...)` | Per-subject attendance | attendance_summary, subjects |
| `get_student_backlog_summary(student_id, ...)` | Backlog accumulation | student_semester_summary |

### B. Subject Analytics (3 methods)

| Method | Grain | Source Tables |
|---|---|---|
| `get_subject_performance_summary(subject_id, ...)` | Single subject aggregate | student_subject_performance, subjects |
| `get_subject_attendance_summary(subject_id, ...)` | Per-student attendance for subject | attendance_summary |
| `get_subject_underperformers(subject_id, ...)` | Students below threshold | student_subject_performance |

### C. Department / Semester Analytics (3 methods)

| Method | Grain | Source Tables |
|---|---|---|
| `get_department_overview(department_code, semester_no)` | Department-wide stats | student_semester_summary, attendance_summary, subjects |
| `get_semester_performance_distribution(semester_no, ...)` | Grade histogram per department | student_subject_performance, students |
| `get_attendance_distribution(semester_no, ...)` | Attendance band histogram | attendance_summary |
| `get_backlog_distribution(semester_no, ...)` | Backlog count histogram | student_semester_summary |

### D. At-Risk Analytics (3 methods)

| Method | Grain | Source Tables |
|---|---|---|
| `get_at_risk_students(department_code, semester_no)` | Composite risk score | student_semester_summary, attendance_summary, student_subject_performance |
| `get_students_below_attendance_threshold(department_code, ...)` | Below threshold list | attendance_summary |
| `get_subjects_needing_attention(department_code, ...)` | Subjects with high fail/drop rates | student_subject_performance, student_subject_enrollment |

---

## Thresholds (from `app.core.config.Settings`)

| Parameter | Default | Used by |
|---|---|---|
| `FACULTY_ATTENDANCE_THRESHOLD` | 75 | At-risk (attendance flag) |
| `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD` | 60 | At-risk (critical flag) |
| `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD` | 90 | Attendance summary banding |
| `FACULTY_MENTEE_BACKLOG_THRESHOLD` | 2 | At-risk (backlog flag) |
| `FACULTY_MENTEE_SGPA_THRESHOLD` | 6.0 | At-risk (SGPA flag) |

---

## Risk Scoring (Category D)

`get_at_risk_students` computes a deterministic 0–100 score:

| Factor | Weight | Formula |
|---|---|---|
| Attendance gap | 33.3% | `max(0, (threshold - actual)) / threshold * 33.3` |
| Backlog pressure | 33.3% | `min(backlogs / 10, 1.0) * 33.3` |
| SGPA gap | 33.3% | `max(0, (threshold - sgpa)) / threshold * 33.3` |

Score = `100 - (attendance_gap + backlog_pressure + sgpa_gap)`. A student is flagged if any reason is triggered.

---

## Schema Notes

- `student_subject_performance` has **no** `academic_year` column (despite accept-phase models listing it). The API accepts `academic_year` for forward compatibility but does not use it in queries.
- `attendance_summary.attendance_status` allows: `Excellent`, `Good`, `Average`, `Low`, `Critical`
- `attendance_summary.eligibility_status` allows: `Eligible`, `Not Eligible`
- `departments` has columns: `dept_code`, `department_name`, `department_short_name`, `degree`, `total_semesters`, `status`

---

## What's NOT Included (V1 Scope)

- ML prediction (deterministic rules only)
- GenAI natural language queries
- Dashboard UI
- Authentication / authorization
- Deployment / production hardening
- Real-time data refresh
- Multi-department or multi-semester analytics (V1 = CSE only)

---

## Usage Example

```python
from app.repositories.analytics_repo import AnalyticsRepository

pool = await create_pool()
repo = AnalyticsRepository(pool)

# Student academic profile
profile = await repo.get_student_academic_profile("STU000001")
print(profile.student_name, profile.cgpa)

# At-risk students in CSE Sem 7
at_risk = await repo.get_at_risk_students(department_code=1, semester_no=7)
for student in at_risk.students:
    print(f"{student.student_name}: {student.risk_score}")
```

---

## Testing

- **Unit tests**: `backend/tests/test_analytics.py` — 41 tests covering all methods, filtering, aggregation, empty results, no-writes, parameterized queries
- **Live verification**: `backend/verify_analytics.py` — 32 checks against live Supabase (all pass)
- **ETL regression**: 286 ETL tests still pass after analytics layer addition

---

## Files

| File | Description |
|---|---|
| `backend/app/repositories/analytics_repo.py` | Repository with 14 read-only query methods |
| `backend/app/schemas/analytics.py` | Pydantic response models for all categories |
| `backend/tests/test_analytics.py` | 41 unit tests |
| `backend/verify_analytics.py` | Live Supabase verification script |
