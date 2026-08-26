# ETL Reconciliation Summary — KDAC-3

**Date:** 26 August 2026
**Status:** Reconciliation Complete
**Scope:** ETL pipeline architecture reconciliation for V1 implementation

---

## 1. Actual Table Inventory and Classification

### 1.1 Master Tables (4)

| Table | PK | Purpose | ETL Access |
|-------|-----|---------|------------|
| `departments` | `dept_code` (integer) | Institutional grouping | Read-only during Stitch |
| `students` | `student_id` (varchar) | Canonical person record | Read during Stitch/validation; **may be updated during Derive ONLY for approved derived columns** |
| `faculty` | `faculty_id` (varchar) | Teaching staff | Read-only during Stitch |
| `subjects` | `subject_id` (varchar) | Academic units | Read-only during Stitch |

**Note on `students` table:**
- Read during Stitch / validation for identity resolution
- May be updated during Derive **ONLY** for these explicitly approved derived columns:
  - `overall_attendance_percentage` (dynamically recomputed by `_recompute_attendance()`)
  - `full_name` (derived from `first_name + ' ' + last_name`)
- All other columns remain read-only for ETL
- Non-regression test excludes these approved derived columns from "students unchanged" assertion

### 1.2 Bridge Tables (2)

| Table | PK | Purpose | ETL Access |
|-------|-----|---------|------------|
| `student_subject_enrollment` | `enrollment_record_id` (varchar) | Student-subject relationship per semester | Read-only during Stitch |
| `faculty_student_map` | `faculty_student_map_id` (varchar) | Faculty-student assignment | Read-only during Stitch |

### 1.3 Canonical/Grain Tables (4) — ETL Load Targets

| Table | PK | Business/Natural Key | Grain | V1 Source |
|-------|-----|---------------------|-------|-----------|
| `daily_attendance_07` | `attendance_id` (integer, synthetic) | `(student_id, subject_id, lecture_date, lecture_number)` | Per-student per-lecture | `daily_attendance_cse_sem7.csv` |
| `weekly_timetable_07` | `timetable_id` (integer/varchar, synthetic) | `(semester_no, subject_id, faculty_id, day_name, slot_no)` | Per-slot per-day | `weekly_timetable_cse_sem7.csv` |
| `student_subject_performance` | `performance_id` (varchar, synthetic) | `(enrollment_record_id)` | Per-enrollment per-semester | Seed only (no V1 CSV source) |
| `attendance` | `attendance_id` (varchar, synthetic) | `(enrollment_record_id)` | Per-enrollment per-semester | Derived from `daily_attendance_07` |

### 1.4 Derived/Gold Tables (1) — ETL Derive Targets

| Table | PK | Business/Natural Key | Grain | Source |
|-------|-----|---------------------|-------|--------|
| `student_semester_summary` | `semester_summary_id` (varchar, synthetic) | `(student_id, semester_no)` | Per-student per-semester | `student_subject_performance` + `attendance` |

### 1.5 Context/Application Tables (5) — Out of V1 ETL Scope

| Table | PK | Purpose |
|-------|-----|---------|
| `lifestyle_survey` | `lifestyle_id` (varchar) | Student lifestyle data |
| `career_preferences` | `career_preference_id` (varchar) | Career preferences |
| `risk_predictions` | `risk_prediction_id` (varchar) | Risk assessment (deterministic) |
| `users` | `user_id` (varchar) | Authentication/accounts |
| `student_messages` | `message_id` (varchar/uuid) | Notifications |

### 1.6 Append-Only Audit Tables (2) — Out of V1 ETL Scope

| Table | PK | Purpose |
|-------|-----|---------|
| `performance_change_log` | `change_id` (bigint, identity) | Marks change audit trail |
| `attendance_change_log` | `change_id` (bigint, identity) | Attendance change audit trail |

### 1.7 ML/Intelligence Tables (2) — Out of V1 ETL Scope

| Table | PK | Purpose |
|-------|-----|---------|
| `ml_predictions` | `prediction_id` (uuid) | ML model outputs |
| `prediction_feedback` | `feedback_id` (uuid) | Faculty feedback on predictions |

### 1.8 Goals Table (1) — Out of V1 ETL Scope

| Table | PK | Purpose |
|-------|-----|---------|
| `student_goals` | `goal_id` (uuid) | Student academic goals |

---

## 2. Naming Discrepancies

### 2.1 Documented Name → Actual Name Mapping

| Document | Documented Name | Actual Name | Notes |
|----------|-----------------|-------------|-------|
| Audit Report | `lifestyle_habits` | `lifestyle_survey` | Different naming convention |
| Audit Report | `extracurricular` | N/A | Not in actual schema |
| Audit Report | `career_interests` | `career_preferences` | Different naming convention |
| Audit Report | `faculty_student_mappings` | `faculty_student_map` | Different naming convention |
| Audit Report | `faculty_teaching_load` | N/A | Not in actual schema |
| Audit Report | `student_risk_assessment` | `risk_predictions` | Different naming convention |
| Audit Report | `student_recommendations` | N/A | Not in actual schema |
| Audit Report | `subject_analytics` | N/A | Not in actual schema |
| Audit Report | `placement_readiness` | N/A | Not in actual schema |
| Data Engineering Plans | `lifestyle_habits` | `lifestyle_survey` | Different naming convention |
| Data Engineering Plans | `career_interests` | `career_preferences` | Different naming convention |

### 2.2 Key Discrepancies

1. **Audit report lists 17 tables** in 4 functional groups (Master/Grain/Context/Intelligence)
2. **Actual schema has 21 tables** (including users, student_messages, student_goals, ml_predictions, prediction_feedback)
3. **Several tables in audit report don't exist**: `extracurricular`, `faculty_teaching_load`, `student_recommendations`, `subject_analytics`, `placement_readiness`
4. **Naming conventions differ** between documents and actual implementation

### 2.3 Recommended Actions

- Use actual table names in all ETL implementation code
- Update documentation to reflect actual schema
- Do NOT rename database tables — adapt ETL to actual names

---

## 3. V1 ETL Scope — Source → Canonical → Derived Mapping

### 3.1 Data Flow Diagram

```
Source CSV Files
    │
    ├─ daily_attendance_cse_sem7.csv (6,150 rows)
    │   │
    │   ├─→ Extract ─→ Validate ─→ Stage ─→ Stitch ─→ Transform
    │   │                                      │
    │   │                                      ├─ Verify student_id exists in students
    │   │                                      ├─ Verify subject_id exists in subjects
    │   │                                      ├─ Verify faculty_id exists in faculty
    │   │                                      └─ Resolve enrollment_record_id
    │   │
    │   ├─→ Load: daily_attendance_07
    │   │   UPSERT on (student_id, subject_id, lecture_date, lecture_number)
    │   │
    │   └─→ Derive: attendance (aggregate)
    │       DELETE + INSERT for (student_id, subject_id, semester_no)
    │       total_classes, attended_classes, attendance_percentage
    │
    └─ weekly_timetable_cse_sem7.csv (15 rows)
        │
        ├─→ Extract ─→ Validate ─→ Stage ─→ Stitch ─→ Transform
        │                                      │
        │                                      ├─ Verify subject_id exists in subjects
        │                                      └─ Verify faculty_id exists in faculty
        │
        └─→ Load: weekly_timetable_07
            UPSERT on (semester_no, subject_id, faculty_id, day_name, slot_no)
```

### 3.2 Stage-by-Stage Database Writes

| Stage | Database Write? | Target Table | Operation |
|-------|----------------|--------------|-----------|
| Extract | NO | — | — |
| Validate | NO | — | — |
| Stage | NO | — | In-memory only |
| Stitch | NO | — | Reads masters only |
| Transform | NO | — | In-memory only |
| Load | YES | `daily_attendance_07` | UPSERT on business key |
| Load | YES | `weekly_timetable_07` | UPSERT on business key |
| Derive | YES | `attendance` | DELETE scope + INSERT |
| Derive | YES | `student_semester_summary` | DELETE scope + INSERT |
| Derive | YES | `students` (approved columns only) | UPDATE derived columns |

### 3.3 Natural Keys / UPSERT Conflict Targets

**Source:** `backend/etl/keys.py` and actual schema analysis

| Target Table | Business Key (UPSERT Conflict Target) | Source Reference |
|---|---|---|
| `daily_attendance_07` | `(student_id, subject_id, lecture_date, lecture_number)` | `ATTENDANCE_ROW_KEY_FIELDS` in keys.py:20 |
| `weekly_timetable_07` | `(semester_no, subject_id, faculty_id, day_name, slot_no)` | App queries in faculty_repo.py |
| `attendance` | `(enrollment_record_id)` | App queries in faculty_repo.py |
| `student_semester_summary` | `(student_id, semester_no)` | App queries in faculty_repo.py |
| `students` (derived columns) | `(student_id)` | PK, UPDATE WHERE student_id = ... |

**Important Notes:**
- `attendance_id`, `timetable_id`, `performance_id`, `semester_summary_id` are **surrogate PKs**, NOT business keys
- Load stage must use business keys for `ON CONFLICT ... DO UPDATE`
- Verify actual database constraints (UNIQUE, PK) before implementing UPSERT
- Application currently uses SELECT FOR UPDATE + INSERT/UPDATE pattern, not ON CONFLICT

---

## 4. Transaction and Recovery Strategy

### 4.1 Transaction Boundaries

**Source:** `backend/etl/db.py`

```python
@asynccontextmanager
async def transaction(pool, *, dry_run=False):
    """Yield a connection inside a single transaction.
    
    Commit on success, rollback on any failure.
    No broad transaction wraps the whole pipeline.
    """
```

**Implemented Strategy:**
- **Per-stage transaction boundary** (not per-pipeline)
- Load stage: transaction per source (or per batch within source)
- Derive stage: single transaction for all derived updates
- Each stage that writes must call `context.assert_writable()` before database access

### 4.2 Rollback Behavior

| Failure Point | Behavior |
|---------------|----------|
| Load failure | Transaction rollback; no partial canonical state |
| Derive failure | Transaction rollback; gold tables unchanged |
| Earlier stages (Extract/Validate/Stage/Stitch/Transform) | No database writes to rollback |

### 4.3 Partial Failure Behavior

- If Load fails mid-way: Rollback entire source load (atomic per source)
- If Derive fails mid-way: Rollback all derives (atomic per stage)
- Quarantined rows are logged, not loaded — no partial state

### 4.4 Rerun/Recovery Behavior

- **Idempotent:** Re-run converges to same state
- **Load:** UPSERT on natural keys prevents duplicates
- **Derive:** Full recompute (DELETE + INSERT in transaction) prevents accumulation
- **Source fingerprinting:** SHA-256 checksums enable version tracking
- **Dry-run mode:** Never touches database; safe for verification

### 4.5 Idempotency Strategy

| Stage | Strategy | Implementation |
|-------|----------|----------------|
| Load | UPSERT on natural keys | `ON CONFLICT (business_key) DO UPDATE` |
| Derive | Full recompute | `DELETE WHERE ... ; INSERT ...` in transaction |
| Stitch/Transform | Stateless | Re-runnable, no side effects |

---

## 5. Non-Regression Verification Strategy

### 5.1 Principle

**Two groups:**
- **Unchanged tables** → exact equality check (row count + deterministic hash)
- **Changed tables** → expected-delta check only

### 5.2 Group A — Tables That Must Remain Completely Unchanged

| Table | Pre-Run Capture | Post-Run Verification |
|-------|-----------------|----------------------|
| `departments` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `faculty` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `subjects` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `student_subject_enrollment` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `faculty_student_map` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `lifestyle_survey` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `career_preferences` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `risk_predictions` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `users` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `student_messages` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `student_goals` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `ml_predictions` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `prediction_feedback` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `performance_change_log` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `attendance_change_log` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `student_subject_performance` | row_count, hash(all rows) | count_before == count_after AND hash_before == hash_after |
| `students` (non-derived columns) | row_count, hash(non-derived columns) | count_before == count_after AND hash_before == hash_after |

**Hash Function:** Deterministic concatenation of all column values per row, then SHA-256 of sorted row hashes.

### 5.3 Group B — Tables That Are Allowed to Change

| Table | Pre-Run Capture | Post-Run Verification |
|-------|-----------------|----------------------|
| `daily_attendance_07` | row_count, max(attendance_id), sample checksums | New rows loaded correctly; count delta = expected (6150 - quarantined) |
| `weekly_timetable_07` | row_count, max(timetable_id) | New rows loaded correctly; count delta = expected (15 - quarantined) |
| `attendance` | row_count, sample values for STU000001/STU000032 | Derived aggregates correct (STU000001 sem-7: 81.11) |
| `student_semester_summary` | row_count, sample SGPA values | Derived summaries correct; count matches student×semester scope |
| `students` (approved derived columns only) | approved derived column values for sample students | `overall_attendance_percentage` updated correctly; `full_name` correct |

### 5.4 Verification SQL Patterns

**Group A — Exact Equality:**
```sql
-- Capture pre-run state
SELECT COUNT(*) AS row_count,
       md5(string_agg(row_hash, '' ORDER BY row_hash)) AS table_hash
FROM (
    SELECT md5(ROW(d.*)::text) AS row_hash
    FROM table_name d
) sub;

-- Verify post-run state identical
-- Assert: pre_count == post_count AND pre_hash == post_hash
```

**Group B — Expected Delta:**
```sql
-- Capture pre-run state
SELECT COUNT(*) AS row_count,
       MAX(id_column) AS max_id,
       -- Sample checksums for key columns
       md5(string_agg(ROW(student_id, subject_id, date_col)::text, '' ORDER BY id)) AS sample_hash
FROM target_table
WHERE scope_filter;

-- Verify post-run state
-- Assert: new rows added, correct values, no unexpected changes
```

### 5.5 What Data Should Be Compared Before vs After

**For Group A (unchanged):**
- Every row in every column must be byte-identical
- Row count must match exactly
- Deterministic hash of all rows must match exactly

**For Group B (changed):**
- Row count delta must match expected (source rows - quarantined)
- New rows must have correct business key values
- Derived values must match seed-verified numbers (e.g., STU000001 sem-7 attendance = 81.11)
- Approved derived columns in `students` must be updated correctly
- No rows should be deleted from Group A tables
- No unexpected columns should change in Group A tables

---

## 6. Remaining Items

### 6.1 Source Dataset Availability Verification Required

Source files exist at:
- `backend/datasets/daily_attendance_cse_sem7.csv`
- `backend/datasets/weekly_timetable_cse_sem7.csv`

**Action:** Verify file accessibility and content before ETL implementation.

### 6.2 Database Constraints Verification Required

Before implementing Load stage UPSERT:
- Verify actual UNIQUE constraints on target tables
- Confirm business key columns match database constraints
- Test UPSERT syntax against actual schema

### 6.3 No Other Blockers Identified

- ETL infrastructure is complete
- Extract + Validate stages are implemented and tested
- Business keys are defined in `keys.py`
- Transaction boundaries are defined in `db.py`
- Schema is documented in this reconciliation

---

## 7. Files to Update/Create

### 7.1 Update Existing

| File | Changes |
|------|---------|
| `plan_25_08/etl_implementation_plan.md` | Apply all corrections from this reconciliation |

### 7.2 Create New

| File | Purpose |
|------|---------|
| `plan_25_08/etl_reconciliation_summary.md` | This document |

---

## 8. Next Steps

After review of this reconciliation:

1. **Implement Stage stage** (in-memory staging)
2. **Write tests** for Stage stage
3. **Verify** non-regression strategy works
4. **STOP** — wait for review before proceeding to Stitch

---

**Reconciliation Status:** COMPLETE
**Awaiting:** Review and approval before implementation
