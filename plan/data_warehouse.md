# Data Warehouse Implementation

## 1. Warehouse Overview

The KenexAI KDAC-3 data warehouse is a student-grain analytical platform built on Supabase PostgreSQL. The warehouse stores master data, transactional/academic facts, context data, and intelligence outputs in 16 live tables organized into 4 functional groups.

**Current Status:** Schema live with seeded data; ETL pipeline partially implemented (Extract + Validate stages only); Load/Derive stages pending.

---

## 2. Warehouse Architecture

### 2.1 Three-Layer Model

| Layer | Purpose | Implementation Status |
|-------|---------|----------------------|
| **Staging** | Raw validated/stitched rows with `run_id` before canonical write | Processing convention only (in-memory); no staging tables in V1 |
| **Canonical** | The 16 live tables in 4 functional groups | Live; seeded with verified data |
| **Gold (Derived)** | `student_semester_summary`, aggregate `attendance`, ETL-maintained derived columns on `students` | Seed data present; ETL derive stage pending |

### 2.2 Student-Grain Model

The analytical center of gravity is **one row per student per subject per semester**, with context joined in as needed. Every gold metric is a deterministic function of canonical facts at this grain.

**Universal Stitching Key:** `Student_ID` (`STU######`) — used to relate the same person across all fact sets.

**Secondary Identifier:** `Enrollment_No` (`2023######`) — preserved for academic-number fidelity, never used as the canonical stitch key.

---

## 3. Schema Implementation

### 3.1 Master Data (4 tables)

| Table | Purpose | Seeded Rows | Status |
|-------|---------|-------------|--------|
| `departments` | Institutional grouping (CSE, BBA) | 2 | Complete |
| `students` | Canonical person-level record; carries stitching key | 50 (STU000001–STU000050) | Complete |
| `faculty` | Teaching/mentoring staff | Multiple | Complete |
| `subjects` | Academic units for performance measurement | Multiple (SUB0001–SUB0056) | Complete |

### 3.2 Transactional/Academic Grain (4 tables)

| Table | Purpose | Seeded Rows | Status |
|-------|---------|-------------|--------|
| `student_subject_enrollment` | Many-to-many (student ↔ subject per semester); grain anchor | 350 (sem-7) + historical | Complete |
| `student_subject_performance` | Subject-level marks/performance outcomes | 3,850 (sem-1 through sem-7 partial) | Complete (sem-7 partial: internal/mid populated, end_sem/total/percentage/grade NULL) |
| `attendance` | Aggregate attendance per (student, subject, semester) | 3,850 (sem-1 seeded; sem-7 derived by ETL) | Complete |
| `student_semester_summary` | Derived semester-level aggregates | 350+ (sem-1 through sem-7) | Complete (seeded; ETL derive pending for new data) |

### 3.3 Context Data (3 tables)

| Table | Purpose | Status |
|-------|---------|--------|
| `lifestyle_survey` | Self-reported lifestyle context (sensitive) | Seeded |
| `career_preferences` | Declared career interests | Seeded |
| `faculty_student_map` | Mentor/advisor relationship (versioned by term) | Seeded (1:1 with students) |

### 3.4 Intelligence Output (3 tables)

| Table | Purpose | Status |
|-------|---------|--------|
| `risk_predictions` | Versioned at-risk predictions with model provenance | 80 rows seeded |
| `genai_insights` | Grounded narrative insights from structured data | Schema ready; no data yet |
| `users` | Authentication and role resolution | Complete |

### 3.5 Operational Tables (2 tables)

| Table | Purpose | Status |
|-------|---------|--------|
| `daily_attendance_07` | Lecture-level attendance (6,150 rows) | Live; CSV source verified |
| `weekly_timetable_07` | Weekly timetable slots (15 rows) | Live; CSV source verified |

---

## 4. ETL Pipeline Implementation

### 4.1 Pipeline Stages (7-Stage Model)

```
Source(s) ──> Extract ──> Validate ──> Stage ──> Stitch ──> Transform ──> Load ──> Derive
               │             │           │         │            │            │        │
               │        quarantine     staging    identity    mapping,     upsert   summary/
               │        on failure     bucket     resolution   derivation   to       gold
               │                                    │                        canonical   tables
               │                             review queue on
               │                             ambiguity
```

### 4.2 Implementation Status

| Stage | Status | Description |
|-------|--------|-------------|
| **Extract** | ✅ Implemented | `backend/etl/stages/extract.py` — reads CSV sources with source identity preserved |
| **Validate** | ✅ Implemented | `backend/etl/stages/validate.py` — schema/integrity/domain/uniqueness checks + quarantine |
| **Stage** | ⏳ Planned | Processing convention only in V1 (in-memory staging) |
| **Stitch** | ⏳ Planned | Identity resolution; canonical key mapping |
| **Transform** | ⏳ Planned | Deterministic mappings and derivations at fact grain |
| **Load** | ⏳ Planned | Upsert transformed rows into canonical tables on natural keys |
| **Derive** | ⏳ Planned | Compute gold-level aggregate tables from canonical facts |

### 4.3 ETL CLI

```bash
# From backend/ directory
python -m etl --help
python -m etl stages                    # List canonical stage names
python -m etl run --dry-run             # Execute without database writes (default)
python -m etl run --apply               # Execute against database
python -m etl run --dry-run --stage extract    # Run single stage
python -m etl run --dry-run --json      # Output run manifest as JSON
```

### 4.4 V1 Scope (Locked)

- **Semester:** 7
- **Department:** CSE (dept_code = 1)
- **Academic Year:** 2026-2027
- **Students:** STU000001–STU000050 (50 students)
- **Subjects:** SUB0050–SUB0056 (7 subjects)
- **Enrollment Rows:** 350 (50 students × 7 subjects)
- **Attendance Rows:** 6,150 (123 lectures)
- **Timetable Rows:** 15

---

## 5. Data Sources

### 5.1 CSV Datasets

| Source | File | Rows | Columns | Status |
|--------|------|------|---------|--------|
| Daily Attendance | `backend/datasets/daily_attendance_cse_sem7.csv` | 6,150 | 13 | Verified |
| Weekly Timetable | `backend/datasets/weekly_timetable_cse_sem7.csv` | 15 | 12 | Verified |

### 5.2 Source-to-Table Mapping

| Source | Target Table | Key Fields |
|--------|-------------|------------|
| `daily_attendance_cse_sem7.csv` | `daily_attendance_07` | `student_id, subject_id, lecture_date, lecture_number` |
| `weekly_timetable_cse_sem7.csv` | `weekly_timetable_07` | `timetable_id, department_code, semester_no, academic_year, day_name, slot_no` |

### 5.3 Source Identity Preservation

Every extracted source carries:
- `checksum_sha256` — file fingerprint for lineage
- `extracted_at` — extraction timestamp
- `row_count` — number of data rows
- `columns` — column names

---

## 6. Validation and Quality

### 6.1 Validation Checklist

| Check | Rule | Failure Behavior |
|-------|------|-----------------|
| Schema | Required columns present, correct types | Quarantine file/row; fail if whole-source |
| Required Keys | `student_id`, `subject_id`, `faculty_id` non-null | Quarantine |
| Referential | student/subject/faculty exist in masters | Quarantine |
| Timetable Coherence | (subject, faculty, day, slot) matches `weekly_timetable_07` | Quarantine |
| Domain | `attendance_status` ∈ {P, A}; dates parse; `lecture_number` positive | Quarantine |
| Uniqueness | Lecture session key unique; individual attendance rows unique | Quarantine / fail |
| Completeness | 50 students per lecture expected | Flag → reconcile |
| Scope | department_code/semester_no/academic_year match run scope | Quarantine |

### 6.2 Quarantine Mechanics

- **No silent drops** — failed rows quarantined with reason
- **No force-match identity** — ambiguous records go to review queue
- **Quarantine ratio gate** — exceeds `ETL_MAX_QUARANTINE_RATIO` (default 0.05) → run exits 1
- **Per-run artifacts** — quarantine records include: `run_id, stage, reason_code, row identity, raw row`

### 6.3 Reconciliation Expectations

| Metric | Expected | Verified Source |
|--------|----------|----------------|
| Daily attendance rows | 6,150 | CSV re-analysis |
| Distinct lectures | 123 | CSV re-analysis |
| Per-subject lecture counts | SUB0050=25, SUB0051=17, SUB0052=8, SUB0053=25, SUB0054=16, SUB0055=16, SUB0056=16 | CSV re-analysis |
| Attendance status counts | P=5,379 / A=771 | CSV re-analysis |
| Distinct (student, subject) pairs | 350 | CSV re-analysis |
| Students per lecture | 50 (uniform) | CSV re-analysis |
| Timetable rows | 15 | File + live table |

---

## 7. Threshold Engine Integration

All bands/thresholds resolve to `backend/app/core/config.py` — never hardcoded in ETL code.

| Domain | Threshold | Value | Usage |
|--------|-----------|-------|-------|
| Attendance | `FACULTY_ATTENDANCE_THRESHOLD` | 75.0 | Eligible ≥ 75, else Not Eligible |
| Attendance | `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD` | 60.0 | `attendance_status = Critical` below 60 |
| Attendance | `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD` | 90.0 | `attendance_status = Excellent` ≥ 90 |
| Performance | `FACULTY_PERFORMANCE_THRESHOLD` | 60.0 | Pass/performance watch |
| Performance | `CRITICAL_PERFORMANCE_THRESHOLD` | 50.0 | Critical performance |
| Performance | `DISTINCTION_GRADE_POINT` | 9.0 | Distinction grade point |
| Marks | `MARKS_PASS_PERCENTAGE` | 40.0 | Pass mark |

---

## 8. Derived Fields (ETL-Maintained)

These fields are derived by ETL (batch) or by the write path (plans 14/15, incremental) — never client-supplied, never hand-maintained.

| Table | Derived Field(s) | Derivation |
|-------|-----------------|------------|
| `students` | `full_name` | `first_name + ' ' + last_name` |
| `students` | `overall_attendance_percentage` | mean of aggregate `attendance_percentage` across all terms |
| `students` | `latest_sgpa` | SGPA of most recent complete term in `student_semester_summary` |
| `students` | `overall_cgpa` | cumulative across complete terms |
| `students` | `overall_percentage` | cumulative percentage across complete terms |
| `students` | `total_credits_registered` / `total_credits_earned` | sum across `student_semester_summary` |
| `students` | `total_backlogs` | count of failed subjects |
| `students` | `academic_standing` | band from CGPA via Threshold Engine |
| `attendance` | `total_classes`, `attended_classes`, `attendance_percentage` | from `daily_attendance_07` via plan-15 formulas |
| `attendance` | `attendance_status`, `eligibility_status`, `shortage_flag`, `remarks` | from bands (config) |
| `student_semester_summary` | all aggregate columns | from `student_subject_performance` + `attendance` |

**Readiness Gate:** Final academic values (SGPA, semester result, credits earned, pass/fail, final percentage) are derived only when required academic facts for that term are complete. Missing final marks are **never** treated as zero.

---

## 9. Lineage and Auditability

### 9.1 Lineage Record Structure

```python
@dataclass(frozen=True)
class LineageRecord:
    run_id: str                    # Unique run identifier
    source: str                    # Source dataset name
    stage: str                     # Pipeline stage
    pipeline_version: str          # Version that transformed the data
    loaded_at: datetime            # When loaded
    entity_type: Optional[str]     # Table/entity name
    natural_key: Optional[Tuple]   # Business key
    source_record_id: Optional[str] # Source-specific ID
    op: str                        # insert/update/noop
    metadata: Any                  # Additional context
```

### 9.2 Audit Alignment

| Trail Type | Owner | Purpose |
|------------|-------|---------|
| **Operator-write** | `performance_change_log` (plan 14), `attendance_change_log` (plan 15) | Who changed what, when, with `updated_by` |
| **Batch-load** | ETL lineage ledger (future) | Which run loaded what, from which source, with which version |

**Write-path precedence:** Faculty Marks/Attendance writes and ETL share canonical fact tables. ETL never overwrites an existing operator-entered canonical fact.

---

## 10. Refresh and Operations

### 10.1 Batch Cadence

- ETL runs invoked explicitly via CLI (`python -m etl run`)
- Freshness watermark rather than scheduled automation
- Future: Airflow/Prefect for scheduling (not V1)

### 10.2 Idempotent Rerun

- Loads upsert on natural keys
- Derives are full recomputes of their grain within the run's transaction
- Failed run leaves no partial canonical state (rollback)
- Re-run converges to same canonical state

### 10.3 Freshness Contract

- Dashboard never waits on ETL
- Consumers read last-known canonical state with watermark
- "Last updated" indicator from lineage ledger

---

## 11. Database Compatibility

| Requirement | How Satisfied |
|-------------|---------------|
| 16 live tables unchanged | ETL loads into existing schema; V1 adds no staging table |
| `daily_attendance_07` / `weekly_timetable_07` | Used as canonical load targets; DDL stubs acknowledged |
| Seeded semester-1 aggregate `attendance` | Preserved untouched; sem-7 aggregate derived by ETL |
| Seeded `student_semester_summary` (sem 1–5) | Preserved as as-of snapshot; gold refresh derives same formulas for new terms |
| Sem-7 `student_subject_performance` (partial marks) | Validated but never overridden; plan 14 is operator path |
| Write-path precedence (plans 14/15) | ETL never overwrites operator-entered canonical facts |
| `risk_predictions` (80 rows) | Prediction outputs with producing version; untouched by ETL |
| RLS off / app-layer authz | Unchanged; ETL runs under service credential |
| Multi-tenancy | Keys carry tenant dimension; ETL scoped by (department_code, semester_no, academic_year) |

---

## 12. Seed Data Verification

### 12.1 Verified Metrics (STU000001)

| Metric | Value | Source |
|--------|-------|--------|
| Sem-7 SGPA | 7.84 | `student_semester_summary` seed |
| Overall CGPA | 7.83 | `students` seed |
| Sem-7 attendance % | 81.11 | Derived from `daily_attendance_07` |
| Overall attendance % | 79.78 | `students.overall_attendance_percentage` |
| Total backlogs | 0 | `students.total_backlogs` |
| Academic standing | Good | `students.academic_standing` |

### 12.2 Seed Row Counts

| Table | Rows | Scope |
|-------|------|-------|
| `departments` | 2 | CSE, BBA |
| `students` | 50 | STU000001–STU000050 |
| `student_subject_enrollment` | 350+ | sem-7 (350) + historical |
| `student_subject_performance` | 3,850 | sem-1 through sem-7 |
| `attendance` (aggregate) | 3,850 | sem-1 seeded; sem-7 derived |
| `student_semester_summary` | 350+ | sem-1 through sem-7 |
| `risk_predictions` | 80 | Seeded |
| `daily_attendance_07` | 6,150 | sem-7 CSE |
| `weekly_timetable_07` | 15 | sem-7 CSE |

---

## 13. Extensibility

### 13.1 Multi-Semester/Multi-Source

- New semesters/departments: data + config, no code change
- New sources: add Extract/Validate adapters; Stitch/Transform/Load/Derive unchanged
- Real staging tables: documented future option (not V1)
- Kafka/Redis/microservices: documented escalation only

### 13.2 ML/GenAI Readiness

- **Features:** canonical student-grain facts + gold derived tables are the training surface
- **Prediction lineage:** `risk_predictions` records model version per row
- **Isolation:** training offline batch; serving lightweight; slow retraining never blocks serving
- **GenAI grounding:** `genai_insights` reproducible from structured source context
- **Explainability:** deterministic, versioned features feed tree-based models (XGBoost) with SHAP values

---

## 14. Relationship to Plan Files

| Document | Relationship |
|----------|-------------|
| `plan/00` | Glossary and canonical terminology |
| `plan/01` | Service boundaries; ETL in FastAPI side |
| `plan/02` | Current state; warehouse not yet ETL-driven |
| `plan/03` | Authority on schema and ETL behavior |
| `plan/04` | Analytics/ML/GenAI engine; feature/version readiness |
| `plan/06` | Delivery roadmap; ETL is module-order step 2 |
| `plan/data_engineering/01` | ETL pipeline architecture and stages |
| `plan/data_engineering/02` | Identity resolution and data stitching |
| `plan/data_engineering/03` | Data quality, warehouse layers, and operations |
| `plan/faculty/14` | Marks entry write path |
| `plan/faculty/15` | Attendance entry write path |
| `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` | Authoritative source for batch/freshness/ML/GenAI expectations |

---

## 15. Implementation Gaps

| Gap | Impact | Priority |
|-----|--------|----------|
| Stage/Stitch/Transform/Load/Derive stages not implemented | Pipeline cannot load new data or refresh derived tables | High |
| Empty migration stubs (`10_weekly_timetable_07.sql`, `11_daily_attendance_07.sql`, `12_indexes.sql`, `13_constraints.sql`) | Tables exist live but have no executable DDL | Medium |
| No lineage ledger table | Audit trail incomplete; no run manifest persistence | Medium |
| No audit change-log tables | `performance_change_log` and `attendance_change_log` planned but no DDL | Medium |
| Analysis JSON staleness | `lecture_analysis.json` reports 107 lectures; actual is 123 | Low (documentation only) |

---

## 16. Key Files Reference

### ETL Implementation
- `backend/etl/__main__.py` — CLI entry point
- `backend/etl/cli.py` — Command-line interface
- `backend/etl/runner.py` — Pipeline runner
- `backend/etl/config.py` — ETL configuration
- `backend/etl/context.py` — Run context
- `backend/etl/sources.py` — CSV extraction
- `backend/etl/validation.py` — Validation rules
- `backend/etl/keys.py` — Business keys
- `backend/etl/lineage.py` — Lineage record structure
- `backend/etl/db.py` — Database access
- `backend/etl/stages/extract.py` — Extract stage
- `backend/etl/stages/validate.py` — Validate stage

### Configuration
- `backend/app/core/config.py` — Threshold Engine and application settings
- `backend/app/core/database.py` — asyncpg pool

### Data
- `backend/datasets/daily_attendance_cse_sem7.csv` — Source attendance data
- `backend/datasets/weekly_timetable_cse_sem7.csv` — Source timetable data

### Migrations
- `migrations/01_departments_data.sql` through `migrations/22_prediction_feedback.sql` — Seed data and schema

### Plan Documents
- `plan/03_database_schema_and_etl_pipeline.md` — Schema authority
- `plan/data_engineering/01_reusable_etl_architecture.md` — ETL pipeline architecture
- `plan/data_engineering/02_data_stitching_and_identity_resolution.md` — Identity resolution
- `plan/data_engineering/03_data_quality_warehouse_and_operations.md` — Data quality and operations
