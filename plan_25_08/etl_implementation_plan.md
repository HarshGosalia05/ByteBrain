# ETL Implementation Plan — KDAC-3

**Date:** 25 August 2026 (Updated: 26 August 2026)
**Scope:** ETL pipeline completion (Extract → Validate → Stage → Stitch → Transform → Load → Derive)
**Status:** Implementation Plan (Reconciled with actual schema)
**Depends On:** `plan/data_engineering/01_reusable_etl_architecture.md`, `plan/data_engineering/02_data_stitching_and_identity_resolution.md`, `plan/data_engineering/03_data_quality_warehouse_and_operations.md`
**Reconciliation:** `plan_25_08/etl_reconciliation_summary.md`

---

## 1. Current ETL Assessment

### 1.1 What Exists (29% Complete)

**Infrastructure Layer (Complete):**

| Component | File | Status |
|-----------|------|--------|
| Configuration | `backend/etl/config.py` | ✅ Complete — reuses app Settings + Threshold Engine |
| Run Context | `backend/etl/context.py` | ✅ Complete — run_id, pipeline metadata |
| Result Model | `backend/etl/result.py` | ✅ Complete — StageResult, RunSummary |
| Exceptions | `backend/etl/exceptions.py` | ✅ Complete — hierarchy + exit codes |
| Business Keys | `backend/etl/keys.py` | ✅ Complete — deterministic keys |
| Lineage | `backend/etl/lineage.py` | ✅ Complete — LineageRecord foundation |
| Logging | `backend/etl/logging.py` | ✅ Complete — structured ETL logging |
| Database | `backend/etl/db.py` | ✅ Complete — asyncpg pool + transaction |
| Stage Contract | `backend/etl/stages/__init__.py` | ✅ Complete — ABC interface |
| Runner | `backend/etl/runner.py` | ✅ Complete — ordered execution, fail-loud |
| CLI | `backend/etl/cli.py` | ✅ Complete — --dry-run/--apply, --stage, --sources |
| Entry Point | `backend/etl/__main__.py` | ✅ Complete — `python -m etl` |

**Extract Stage (Complete):**

| Component | File | Status |
|-----------|------|--------|
| CSV Extraction | `backend/etl/sources.py` | ✅ Complete — source identity, checksums, timestamps |
| ExtractStage | `backend/etl/stages/extract.py` | ✅ Complete — reads CSV sources |

**Validate Stage (Complete):**

| Component | File | Status |
|-----------|------|--------|
| Validation Rules | `backend/etl/validation.py` | ✅ Complete — schema/integrity/domain/uniqueness |
| ValidateStage | `backend/etl/stages/validate.py` | ✅ Complete — quarantine logic |

**Tests (Complete for Extract + Validate):**

| Test File | Coverage |
|-----------|----------|
| `test_etl_foundation.py` | Runner, context, keys, dry-run guard |
| `test_etl_extract_validate.py` | Extract + Validate comprehensive tests |
| `test_etl_cli.py` | CLI argument parsing and commands |

### 1.2 What's Missing (71% - 5 Stages)

| Stage | Component | Status | Impact |
|-------|-----------|--------|--------|
| **Stage** | In-memory staging convention | ⏳ Not Implemented | Processing bucket for validated/stitched rows |
| **Stitch** | Identity resolution logic | ⏳ Not Implemented | Canonical Student_ID mapping |
| **Transform** | Deterministic mappings | ⏳ Not Implemented | Semantic normalization at fact grain |
| **Load** | Canonical table upserts | ⏳ Not Implemented | Database writes on natural keys |
| **Derive** | Gold-level aggregations | ⏳ Not Implemented | student_semester_summary, aggregate attendance |

### 1.3 What Works Today

```bash
# Extract + Validate in dry-run mode
python -m etl run --dry-run

# Single stage execution
python -m etl run --stage extract
python -m etl run --stage validate

# Source-scoped runs
python -m etl run --sources daily_attendance
python -m etl run --sources weekly_timetable
```

**Verified behavior:**
- Extract reads 6,150 attendance rows + 15 timetable rows
- Validate quarantines invalid records with full audit context
- Quarantine ratio gate (5%) fails loud when exceeded
- Dry-run never touches the database
- CLI reports per-stage timing and row counts

### 1.4 Reconciliation Completed

**See:** `plan_25_08/etl_reconciliation_summary.md` for:
- Actual table inventory and classification (21 tables)
- Naming discrepancies between documents and actual schema
- Source → canonical → derived mapping
- Business keys / UPSERT conflict targets
- Transaction and recovery strategy
- Non-regression verification strategy (two groups)

---

## 2. ETL Pipeline Architecture

### 2.1 Seven-Stage Model (from `plan/data_engineering/01`)

```
Source(s) ──> Extract ──> Validate ──> Stage ──> Stitch ──> Transform ──> Load ──> Derive
               │             │           │         │            │            │        │
               │        quarantine     staging    identity    mapping,     upsert   summary/
               │        on failure     bucket     resolution   derivation   to       gold
               │                                    │                        canonical   tables
               │                             review queue on
               │                             ambiguity
```

### 2.2 Stage Responsibilities

| Stage | Input | Output | Database? |
|-------|-------|--------|-----------|
| **Extract** | CSV files | Raw rows + source metadata | No |
| **Validate** | Raw rows | Validated rows + quarantine log | No |
| **Stage** | Validated rows | In-memory bucket with run_id | No |
| **Stitch** | Staged rows | Rows on canonical keys | No (reads masters) |
| **Transform** | Stitched rows | Canonical-shaped rows | No |
| **Load** | Transformed rows | Canonical tables updated | Yes (upsert) |
| **Derive** | Canonical facts | Gold tables refreshed | Yes (delete+insert) |

### 2.3 Key Design Principles (from `plan/data_engineering/01`)

| # | Principle | Implementation |
|---|-----------|----------------|
| P1 | Fail loudly | Non-zero exit code + structured error on any failure |
| P2 | Deterministic | Same input → same business results (run_id/timestamps may differ) |
| P3 | Idempotent | Re-run converges to same state (upserts + full recompute) |
| P4 | Batch, out of request path | ETL never blocks dashboard loads |
| P5 | Two-sources-of-truth prevention | One fact source per metric |
| P6 | Quarantine, never silently drop | Failed rows logged with reason |
| P7 | Stitch before load | Map to Student_ID during staging |
| P8 | Auditable | Every row traceable to source + pipeline version + run |
| P9 | Preserve history | Academic facts keep semester history |
| P10 | Reuse-first | Compose existing pieces (Threshold Engine, asyncpg) |

---

## 3. Implementation Plan

### 3.1 Stage 1: In-Memory Staging (`backend/etl/stages/stage.py`)

**Purpose:** Hold validated/stitched rows in memory with run_id for the duration of the run. No new tables.

**Implementation:**
```python
class StageStage(Stage):
    """In-memory staging bucket (processing convention only in V1)."""
    
    name = "stage"
    
    async def run(self, context, pool=None):
        # Read from shared["validated"] (output of Validate stage)
        # Tag each row with run_id
        # Store in shared["staged"]
        # Return StageResult with rows_read, rows_accepted
```

**Key Requirements:**
- Rows held in memory with run_id metadata
- No database writes
- Deterministic ordering
- Pass-through for V1 (no transformation)

**Verification:**
- Row counts match Validate output
- run_id attached to all staged rows
- No database writes in dry-run or apply mode

---

### 3.2 Stage 2: Identity Resolution (`backend/etl/stages/stitch.py`)

**Purpose:** Resolve every row to canonical identity keys (Student_ID, Subject_ID, Faculty_ID, enrollment_record_id).

**Implementation:**
```python
class StitchStage(Stage):
    """Resolve rows to canonical identity keys."""
    
    name = "stitch"
    
    async def run(self, context, pool=None):
        # Read masters from database (students, subjects, faculty, enrollment)
        # For each staged row:
        #   1. Resolve student_id → students table
        #   2. Resolve subject_id → subjects table
        #   3. Resolve faculty_id → faculty table
        #   4. Resolve enrollment_record_id → student_subject_enrollment
        #   5. Verify all FKs exist
        #   6. Ambiguous → review queue (EtlStitchAmbiguityError)
        # Store in shared["stitched"]
```

**Key Requirements:**
- Read masters from database (asyncpg)
- Verify all foreign keys exist
- Log confidence/method for each resolution
- Route ambiguous records to review queue
- Never force-match or silently drop

**Verification:**
- Every stitched row has valid Student_ID, Subject_ID, Faculty_ID
- enrollment_record_id resolves to existing enrollment
- No orphan records (FK violations logged)
- Ambiguous records counted and reported

---

### 3.3 Stage 3: Semantic Normalization (`backend/etl/stages/transform.py`)

**Purpose:** Apply deterministic mappings and derivations at the fact grain.

**Implementation:**
```python
class TransformStage(Stage):
    """Deterministic mappings and derivations at fact grain."""
    
    name = "transform"
    
    async def run(self, context, pool=None):
        # For each stitched row:
        #   1. Parse dates (lecture_date → datetime.date)
        #   2. Parse times (start_time, end_time → datetime.time)
        #   3. Normalize strings (strip whitespace, case normalization)
        #   4. Enrich subject_name from subjects table
        #   5. Derive lecture_session_key
        #   6. Apply Threshold Engine bands (attendance_status, eligibility)
        # Store in shared["transformed"]
```

**Key Requirements:**
- Date/timestamp normalization (ISO format)
- String normalization (trim, case)
- Code → name enrichment (subject_name from subjects)
- Threshold Engine integration (no hardcoded values)
- No summarization (deferred to Derive)

**Verification:**
- Dates parse correctly
- Strings normalized consistently
- subject_name matches subjects table
- Threshold bands applied correctly

---

### 3.4 Stage 4: Canonical Table Upsert (`backend/etl/stages/load.py`)

**Purpose:** Safely persist transformed rows into canonical tables using natural-key upserts.

**Implementation:**
```python
class LoadStage(Stage):
    """Upsert transformed rows into canonical tables."""
    
    name = "load"
    
    async def run(self, context, pool=None):
        context.assert_writable()
        # Begin transaction
        # For each transformed row:
        #   1. Build UPSERT SQL (ON CONFLICT ... DO UPDATE)
        #   2. Execute with asyncpg
        #   3. Track insert/update/noop counts
        # Commit transaction
        # Return StageResult with load statistics
```

**Key Requirements:**
- UPSERT on natural keys (not INSERT)
- Per-stage transaction boundary (rollback on failure)
- Preserve existing operator-entered values
- Track insert/update/noop counts
- Never overwrite history outside defined semantics

**Verification:**
- Natural keys respected (no duplicates)
- Existing records updated, not overwritten
- Transaction rollback on failure
- Load statistics reported

---

### 3.5 Stage 5: Gold-Level Aggregation (`backend/etl/stages/derive.py`)

**Purpose:** Compute gold-level aggregate tables from canonical facts.

**Implementation:**
```python
class DeriveStage(Stage):
    """Compute gold-level aggregates from canonical facts."""
    
    name = "derive"
    
    async def run(self, context, pool=None):
        context.assert_writable()
        # Begin transaction
        # 1. Derive aggregate attendance from daily_attendance_07
        #    - total_classes = count distinct (lecture_date, lecture_number)
        #    - attended_classes = count 'P'
        #    - attendance_percentage = attended/total × 100
        #    - Apply Threshold Engine bands
        # 2. Derive student_semester_summary from performance + attendance
        #    - subjects_registered, credits, totals, SGPA
        #    - Apply readiness gate (final values only when complete)
        # 3. Update derived columns on students table
        # Commit transaction
        # Return StageResult with derive statistics
```

**Key Requirements:**
- Full recompute (delete + rebuild within transaction)
- Plan-15 formulas for attendance derivation
- Readiness gate for final values (SGPA, semester result)
- No fabrication from incomplete data
- Idempotent (re-run produces same results)

**Verification:**
- Aggregate attendance matches expected (STU000001 sem-7: 81.11)
- student_semester_summary correct
- No duplicate derived records
- Incomplete terms remain partial/NULL

---

## 4. Data Flow Architecture

### 4.1 V1 Source Data

| Source | Rows | Key Fields |
|--------|------|------------|
| `daily_attendance_cse_sem7.csv` | 6,150 | student_id, subject_id, lecture_date, lecture_number |
| `weekly_timetable_cse_sem7.csv` | 15 | timetable_id, subject_id, faculty_id, day_name, slot_no |

### 4.2 Canonical Tables (Load Targets)

| Table | Grain | Business/Natural Key (UPSERT Conflict) | Surrogate PK |
|-------|-------|----------------------------------------|--------------|
| `daily_attendance_07` | (student, subject, lecture_date, lecture_number) | `(student_id, subject_id, lecture_date, lecture_number)` | attendance_id |
| `weekly_timetable_07` | (semester, subject, faculty, day, slot) | `(semester_no, subject_id, faculty_id, day_name, slot_no)` | timetable_id |
| `student_subject_enrollment` | (student, subject, semester, academic_year) | `(enrollment_record_id)` | enrollment_record_id |
| `student_subject_performance` | (student, subject, semester) | `(enrollment_record_id)` | performance_id |

**Note:** `student_subject_enrollment` and `student_subject_performance` are read-only for V1 ETL — no CSV sources load into them.

### 4.3 Gold Tables (Derive Targets)

| Table | Grain | Business/Natural Key | Source |
|-------|-------|---------------------|--------|
| `attendance` (aggregate) | (student, subject, semester) | `(enrollment_record_id)` | `daily_attendance_07` |
| `student_semester_summary` | (student, semester) | `(student_id, semester_no)` | `student_subject_performance` + `attendance` |
| `students` (approved derived columns only) | (student) | `(student_id)` | `attendance` for `overall_attendance_percentage` |

**Note:** `students` table is read-only EXCEPT for explicitly approved derived columns:
- `overall_attendance_percentage` — recomputed by Derive stage
- `full_name` — derived from `first_name + ' ' + last_name`

### 4.4 Table Classification (Reconciled)

**Master Tables (Read-only during Stitch):**
- `departments`, `faculty`, `subjects`

**Master Table with Approved Updates:**
- `students` — read during Stitch; updated during Derive ONLY for `overall_attendance_percentage` and `full_name`

**Bridge Tables (Read-only during Stitch):**
- `student_subject_enrollment`, `faculty_student_map`

**Canonical/Grain Tables (ETL Load Targets):**
- `daily_attendance_07`, `weekly_timetable_07`

**Derived/Gold Tables (ETL Derive Targets):**
- `attendance`, `student_semester_summary`

**Out of V1 ETL Scope:**
- Context: `lifestyle_survey`, `career_preferences`, `risk_predictions`, `users`, `student_messages`
- Audit: `performance_change_log`, `attendance_change_log`
- ML: `ml_predictions`, `prediction_feedback`
- Goals: `student_goals`

---

## 5. Verification Strategy

### 5.1 Unit Tests (per stage)

| Stage | Test File | Coverage |
|-------|-----------|----------|
| Stage | `test_etl_stage.py` | In-memory staging, run_id tagging |
| Stitch | `test_etl_stitch.py` | FK resolution, ambiguity handling |
| Transform | `test_etl_transform.py` | Date parsing, normalization, thresholds |
| Load | `test_etl_load.py` | Upsert semantics, transaction safety |
| Derive | `test_etl_derive.py` | Aggregation formulas, idempotency |

### 5.2 Integration Tests (pipeline)

| Test | Description |
|------|-------------|
| `test_etl_pipeline_e2e.py` | Full pipeline: Extract → Validate → Stage → Stitch → Transform → Load → Derive |
| `test_etl_idempotency.py` | Run pipeline twice, verify no duplicates |
| `test_etl_failure_recovery.py` | Controlled failure, verify rollback + recovery |

### 5.3 Data Verification Tests

| Test | Description |
|------|-------------|
| `test_etl_attendance_derivation.py` | Verify STU000001 sem-7 avg = 81.11 |
| `test_etl_semester_summary.py` | Verify SGPA calculation correctness |
| `test_etl_source_to_output.py` | Trace entity through full pipeline |

### 5.4 Non-Regression Verification (Two Groups)

**Principle:** Unchanged tables → exact equality check. Changed tables → expected-delta check.

**Group A — Must Remain Completely Unchanged:**

| Table | Pre-Run Capture | Post-Run Verification |
|-------|-----------------|----------------------|
| `departments` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `faculty` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `subjects` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `student_subject_enrollment` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `faculty_student_map` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `lifestyle_survey` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `career_preferences` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `risk_predictions` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `users` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `student_messages` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `student_goals` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `ml_predictions` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `prediction_feedback` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `performance_change_log` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `attendance_change_log` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `student_subject_performance` | row_count, hash(all rows) | count == pre_count AND hash == pre_hash |
| `students` (non-derived columns) | row_count, hash(non-derived cols) | count == pre_count AND hash == pre_hash |

**Group B — Allowed to Change, Verify Expected Delta Only:**

| Table | Pre-Run Capture | Post-Run Verification |
|-------|-----------------|----------------------|
| `daily_attendance_07` | row_count, max(attendance_id), sample checksums | New rows loaded; count delta = expected |
| `weekly_timetable_07` | row_count, max(timetable_id) | New rows loaded; count delta = expected |
| `attendance` | row_count, sample values for STU000001/STU000032 | Derived aggregates correct (STU000001 sem-7: 81.11) |
| `student_semester_summary` | row_count, sample SGPA values | Derived summaries correct; count matches scope |
| `students` (approved derived columns only) | approved derived column values | `overall_attendance_percentage` updated correctly |

**Hash Function:** Deterministic concatenation of all column values per row, then SHA-256 of sorted row hashes.

---

## 6. Implementation Sequence

### Phase 1: Stage + Stitch (Week 1)
1. Implement `StageStage` (in-memory staging)
2. Implement `StitchStage` (identity resolution)
3. Write unit tests for both stages
4. Verify with real dataset

### Phase 2: Transform + Load (Week 2)
1. Implement `TransformStage` (semantic normalization)
2. Implement `LoadStage` (canonical upserts)
3. Write unit tests for both stages
4. Verify transaction safety

### Phase 3: Derive (Week 3)
1. Implement `DeriveStage` (gold aggregations)
2. Integrate Plan-15 formulas
3. Implement readiness gate
4. Write derivation verification tests

### Phase 4: Integration + Verification (Week 4)
1. Write full pipeline integration tests
2. Run idempotency verification
3. Run incremental/source-change tests
4. Produce final test report

---

## 7. Risk Mitigation

### 7.1 High-Risk Areas

| Risk | Mitigation |
|------|------------|
| Stitch ambiguity | Review queue + explicit logging; never force-match |
| Load corruption | Per-stage transaction boundary; rollback on failure |
| Derive incorrectness | Reuse Plan-15 formulas; verify against seed data |
| Idempotency failure | UPSERT on natural keys; full recompute for derives |
| Performance | V1 data volume (6,150 rows) is well within single-process capacity |
| Wrong UPSERT keys | Use business keys from keys.py, not surrogate PKs; verify DB constraints |

### 7.2 Rollback Strategy

**Source:** `backend/etl/db.py`

- **Load failure:** Transaction rollback; no partial canonical state
- **Derive failure:** Transaction rollback; gold tables unchanged
- **Pipeline failure:** Non-zero exit code; next run recovers from last successful stage
- **Dry-run mode:** Never touches database; safe for verification

### 7.3 Business Keys (Reconciled)

| Target Table | Business Key (UPSERT Conflict) | Source |
|---|---|---|
| `daily_attendance_07` | `(student_id, subject_id, lecture_date, lecture_number)` | `ATTENDANCE_ROW_KEY_FIELDS` in keys.py |
| `weekly_timetable_07` | `(semester_no, subject_id, faculty_id, day_name, slot_no)` | App queries in faculty_repo.py |
| `attendance` | `(enrollment_record_id)` | App queries in faculty_repo.py |
| `student_semester_summary` | `(student_id, semester_no)` | App queries in faculty_repo.py |

**Note:** Application currently uses SELECT FOR UPDATE + INSERT/UPDATE pattern, not ON CONFLICT. ETL should use ON CONFLICT for idempotency.

---

## 8. Acceptance Criteria Checklist

- [ ] Source extraction works (6,150 + 15 rows)
- [ ] Validation works (quarantine + ratio gate)
- [ ] Staging works (in-memory bucket with run_id)
- [ ] Stitching works (FK resolution, ambiguity handling)
- [ ] Transformations work (date parsing, normalization, thresholds)
- [ ] Loading works (UPSERT on business keys, not surrogate PKs)
- [ ] Derivation works (aggregate attendance, semester summary)
- [ ] Source-to-output relationships correct
- [ ] Invalid records handled visibly
- [ ] Duplicate behavior controlled
- [ ] ETL safely repeatable (idempotent)
- [ ] ETL run statistics available
- [ ] Errors logged with context
- [ ] Representative output values manually verified
- [ ] Existing application functionality still works
- [ ] No source data accidentally modified
- [ ] ETL executable from documented command
- [ ] Non-regression: Group A tables unchanged (exact equality)
- [ ] Non-regression: Group B tables changed as expected (delta check)
- [ ] Students table: only approved derived columns updated

---

## 9. Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `backend/etl/stages/stage.py` | In-memory staging stage |
| `backend/etl/stages/stitch.py` | Identity resolution stage |
| `backend/etl/stages/transform.py` | Semantic normalization stage |
| `backend/etl/stages/load.py` | Canonical table upsert stage |
| `backend/etl/stages/derive.py` | Gold-level aggregation stage |
| `backend/tests/test_etl_stage.py` | Unit tests for Stage stage |
| `backend/tests/test_etl_stitch.py` | Unit tests for Stitch stage |
| `backend/tests/test_etl_transform.py` | Unit tests for Transform stage |
| `backend/tests/test_etl_load.py` | Unit tests for Load stage |
| `backend/tests/test_etl_derive.py` | Unit tests for Derive stage |
| `backend/tests/test_etl_pipeline_e2e.py` | Integration tests |
| `backend/tests/test_etl_idempotency.py` | Idempotency verification |
| `backend/tests/test_etl_non_regression.py` | Non-regression verification (two groups) |

### Modified Files
| File | Change |
|------|--------|
| `backend/etl/cli.py` | Register new stages |
| `backend/etl/__init__.py` | Export new stage classes |
| `backend/etl/stages/__init__.py` | Add stage name constants |

### Documentation Files
| File | Change |
|------|--------|
| `plan_25_08/etl_implementation_plan.md` | Updated with reconciliation findings |
| `plan_25_08/etl_reconciliation_summary.md` | New reconciliation summary |

---

## 10. Final Test Report Template

### A. Existing ETL Functionality
- Extract: CSV reading with source identity
- Validate: Schema/integrity/domain/uniqueness checks + quarantine
- Infrastructure: Config, context, results, exceptions, keys, lineage, logging, DB, CLI

### B. Implemented ETL Functionality
- Stage: In-memory staging bucket
- Stitch: Identity resolution (FK mapping)
- Transform: Semantic normalization + threshold integration
- Load: Canonical table UPSERT with transaction safety
- Derive: Gold-level aggregation (attendance + semester summary)

### C. Files Created/Modified
- [List exact files]

### D. Pipeline Status
```
Source → Extract [DONE] → Validate [DONE] → Stage [DONE] → Stitch [DONE] → Transform [DONE] → Load [DONE] → Derive [DONE]
```

### E. Verification Results
- Source counts: 6,150 + 15
- Processed counts: [actual]
- Rejected counts: [actual]
- Loaded counts: [actual]
- Duplicate counts: [actual]
- Validation results: [actual]
- Idempotency results: [actual]
- Representative data checks: [actual]

### F. Remaining ETL Issues
- [List only ETL-related issues]

### G. Final ETL Status
- [ ] COMPLETE
- [ ] PARTIALLY COMPLETE
- [ ] BLOCKED

---

## 11. Execution Command

```bash
# Full pipeline (dry-run)
python -m etl run --dry-run

# Full pipeline (apply)
python -m etl run --apply

# Single stage
python -m etl run --stage stitch
python -m etl run --stage transform
python -m etl run --stage load
python -m etl run --stage derive

# Source-scoped
python -m etl run --sources daily_attendance --apply

# With JSON manifest
python -m etl run --apply --json
```
