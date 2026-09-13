# Data Engineering — Data Quality, Warehouse & Operations

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Data Engineering → Data Quality, Warehouse & Operations

**Architecture:** Layer-disciplined (staging → canonical → gold), quarantine-first, lineage-led — batch refresh with freshness watermark, fully compatible with the existing 16-table schema

**Depends On:** `plan/data_engineering/01_reusable_etl_architecture.md`, `plan/data_engineering/02_data_stitching_and_identity_resolution.md`, `plan/03` §11 (quality/audit/refresh), `plan/06` (quality gates), `backend/app/core/config.py` (Threshold Engine), plans `14` (Marks Entry) and `15` (Attendance Entry), `backend/analysis/*.json` + `backend/datasets/*.csv` (verification evidence)

## 0. Position in the Project

This is the third of three Data Engineering planning documents. It is a **design specification only** — no code, no schema change, no implementation. It defines how the ETL pipeline keeps the warehouse trustworthy: the layer model (staging / canonical / gold), the validation and reconciliation matrix, quarantine, lineage and auditability, refresh and operations, and the derived-field maintenance matrix.

The blueprint (`plan/03` §11) requires the warehouse to be "designed for correctness and traceability, not just for storage": validate schema/integrity/completeness before load; preserve historical review of when data was ingested, which source produced it, and which pipeline version transformed it; and expose freshness rather than pretending to be live.

**V1 scope is locked:** Semester 7, CSE, 2026-27, subjects SUB0050–SUB0056, students STU000001–STU000050. The reconciliation matrix below records the **currently verified state** of the datasets and live tables — including one discovered discrepancy that the pipeline must codify.

---

## 1. Warehouse Layer Model

### 1.1 Three Layers (V1)

| Layer | What lives there | Source of truth | Notes |
|---|---|---|---|
| **Staging** | Raw validated/stitched rows with `run_id`, before any canonical write | Source datasets | **Processing convention only in V1** — no staging tables (`01` §7.2). Held in-memory for the run, never persisted as a new table. |
| **Canonical** | The 16 live tables in 4 functional groups (master / transactional / context / intelligence) | Loaded from staging via natural-key upserts | This is the existing schema, unchanged. The read contract for every Faculty/Student/analytics query. |
| **Gold (derived)** | `student_semester_summary` rows, aggregate `attendance` rows, ETL-maintained derived columns on `students` | Derived from canonical facts by the Derive stage (`01` §3.1) | Reproducible from facts (P2/P5); refreshed on the ETL cadence, never hand-maintained. |

### 1.2 Grain Discipline (`plan/03` §3.4)

- Raw/transactional facts → canonical (transactional/academic grain).
- Derived summaries → gold (`student_semester_summary`).
- Predictions → `risk_predictions`; narratives → `genai_insights` (each records its producing version).
- No mixing of operational records and derived summaries at the same conceptual level; no two sources of truth for the same metric.

### 1.3 Student-Grain Warehouse

The analytical center of gravity is **one row per student per subject per semester**, with context joined in as needed (`plan/03` §3.1). Every gold metric is a deterministic function of canonical facts at this grain.

---

## 2. Bands and Thresholds (Reuse the Threshold Engine)

Every band used in Validate/Transform/Derive resolves to `backend/app/core/config.py` — never hardcoded in ETL code.

| Domain | Constant (config) | Value | Used for |
|---|---|---|---|
| Attendance | `FACULTY_ATTENDANCE_THRESHOLD` | 75.0 | Eligible ≥ 75, else Not Eligible; shortage Yes < 75 |
| Attendance | `FACULTY_ATTENDANCE_CRITICAL_THRESHOLD` | 60.0 | `attendance_status = Critical` below 60 |
| Attendance | `FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD` | 90.0 | `attendance_status = Excellent` ≥ 90; banding 75–90 = Average/Good |
| Performance | `FACULTY_PERFORMANCE_THRESHOLD` | 60.0 | Pass/performance watch |
| Performance | `CRITICAL_PERFORMANCE_THRESHOLD` | 50.0 | Critical performance |
| Performance | `DISTINCTION_GRADE_POINT` | 9.0 | Distinction grade point |
| Performance | pass-rate watch / healthy | 80.0 / 90.0 | Governance bands |
| Workload | weeks, capacity, overload/underutilized | 15 / 24 h/wk / 0.90 / 0.40 | Workload governance (read-side only; not a V1 ETL input) |
| Marks | pass mark / grade bands | 40 / locked bands | Marks validation + derive (plan 14) |

---

## 3. Validation and Reconciliation Matrix

### 3.1 Source Dataset Facts (Verified)

| Dataset / table | Measured | Source of evidence |
|---|---|---|
| `daily_attendance_cse_sem7.csv` rows | **6,150** data rows | file + live `daily_attendance_07` |
| Distinct lectures (subject, date, number) | **123** | re-analysis of CSV |
| Per-subject lecture counts | SUB0050=25, SUB0051=17, SUB0052=8, SUB0053=25, SUB0054=16, SUB0055=**16**, SUB0056=**16** | re-analysis of CSV |
| `attendance_status` counts | P=5,379 / A=771 | re-analysis of CSV |
| Distinct (student, subject) pairs | 350 | re-analysis (50 students × 7 subjects) |
| Students per lecture | 50 (uniform) | re-analysis |
| `weekly_timetable_cse_sem7.csv` rows | 15 | file + live `weekly_timetable_07` |
| Timetable verified | PK `timetable_id` bigint; FKs dept/faculty/subject; unique `unique_timetable_slot`; 0 nulls/orphans/duplicates; seq next_val 17 | `backend/analysis/verification_results.json` |
| Sem-7 enrollment rows | 350 (50 students × 7 subjects) | `backend/analysis/attendance_analysis.json` |
| Aggregate `attendance` seeded | 3,850 rows (one per enrollment, all terms; sem-7 not seeded) | `migrations/13_attendance_data.sql` |
| Sem-7 performance rows | 350 (marks `NULL`, internal/mid populated) | `backend/analysis/attendance_analysis.json` |
| Teaching days | 41 (Mon 9 / Tue 8 / Wed 8 / Thu 8 / Fri 8); lectures/day 3/3/3/2/2 | `backend/analysis/lecture_analysis.json` |

### 3.2 Discovered Discrepancy (Must Be Codified)

`backend/analysis/lecture_analysis.json` reports **107 total lectures** and **5,350 attendance rows** (SUB0055=8, SUB0056=8). Direct re-analysis of the CSV shows **123 lectures** and **6,150 rows** (SUB0055=16, SUB0056=16). The analysis artifact is **stale or was computed with a different definition** (e.g., Theory-only counting) and must not be used as the load expectation.

**Pipeline rule:** the **source dataset itself** (or the live `daily_attendance_07` table) is the expectation baseline for row/lecture counts, and analysis JSONs are treated as read-only reports, never as load config. Any count drift between a source and the live table is a reconciliation finding, not a silent accept.

### 3.3 Validation Checklist (Validate Stage)

| Check | Rule | Failure → |
|---|---|---|
| Schema | Required columns present, correct types | Quarantine file/row; fail if whole-source |
| Required keys | `student_id`, `subject_id`, `faculty_id` (daily); `subject_id`, `faculty_id`, slot (timetable) non-null | Quarantine |
| Referential | student/subject/faculty exist in masters | Quarantine |
| Timetable coherence | (subject, faculty, day, slot) matches `weekly_timetable_07`; `unique_timetable_slot` respected | Quarantine |
| Domain | `attendance_status` ∈ {P, A}; dates parse; `lecture_number` positive | Quarantine |
| Uniqueness | Lecture session key `(subject_id, lecture_date, lecture_number)` unique in scope (no duplicate lectures); individual attendance rows unique on the attendance-row key `(student_id, subject_id, lecture_date, lecture_number)` | Quarantine / fail |
| Completeness | 50 students per lecture (expectation from 350 pairs) | Flag → reconcile |
| Scope | department_code / semester_no / academic_year match run scope | Quarantine (wrong-semester data) |
| Marks | performance rows resolve to an enrollment; marks within maxima. **Incomplete ≠ zero:** missing final marks (e.g., Semester-7 `end_sem`/`total`/`percentage`/`grade`/`result_status` NULL today) are absent, never defaulted to 0 | Quarantine (plan 14 interplay) |

Quarantine thresholds and the review queue are in §4.

---

## 4. Quarantine and Review Design

### 4.1 Principles (Locked)

- **Never silently drop** (`plan/03` §9.3, blueprint §11). Records with schema problems, missing critical values, or quality failures are quarantined **and logged** with a reason.
- **Never force-match identity** (`plan/03` §10.2). Ambiguous/unmatched identity records go to the review queue.
- Data loss and mismatched identity are both worse than a delayed record (blueprint §12).

### 4.2 V1 Quarantine Mechanics (No New Tables)

In V1 (no staging tables, `01` §7.2), quarantine is a **per-run artifact**:

- Every row that fails a Validate/Stitch check is written to the run's quarantine record: `run_id, stage, reason_code, row identity (keys present), raw row payload`.
- The run manifest (`01` §6) summarizes quarantine counts by reason code.
- If the quarantined ratio for a source exceeds `ETL_MAX_QUARANTINE_RATIO` (config, default small), the run exits 1 — fail loud rather than "success with garbage".
- A review queue is the human-facing list of identity-ambiguous records (future multi-source phases); V1's self-keyed sources rarely produce these, but the mechanism is specified (§5.2 in `02`).

### 4.3 Resolution Discipline

Quarantine is not a dumpster. Each quarantined row must be either: re-submitted with a fix in a later run (idempotence makes this safe), or explicitly acknowledged. Nothing is silently absent from the canonical state; the lineage ledger records both load and quarantine.

---

## 5. Lineage and Auditability

### 5.1 The Lineage Ledger (Planned — No DDL Yet)

The blueprint (`plan/03` §11.2) requires historical review of: when data was ingested, which source produced it, which pipeline version transformed it, which model version produced a prediction, and which context supported a narrative. V1 specifies a lineage ledger (future table, e.g., `etl_run_log` / `etl_entity_log`) capturing:

| Field | Purpose |
|---|---|
| `run_id` | Unique run |
| `pipeline_version` | Which pipeline version transformed the data |
| `started_at` / `finished_at` / `status` | When it ran, and outcome |
| `source` + `source_fingerprint` (file checksum / table + scoped key) | Which source produced the rows |
| per-entity row: `entity_type` + `natural_key` + `op` (insert/update/noop) | Traceability of every loaded row |
| `quarantine` / `review` counts | Completeness of the run |
| `etl_maintained_fields` snapshot | Which derived fields were refreshed |

This is **planned DDL** for the implementation phase — it is not created here and not part of the 16-table schema today.

### 5.2 Audit Alignment with Plans 14/15

- `performance_change_log` (plan 14) and `attendance_change_log` (plan 15) are the **operator-write** audit trails (who changed what, when, with `updated_by`).
- The ETL lineage ledger is the **batch-load** audit trail (which run loaded what, from which source, with which version).
- **Write-path precedence:** Faculty Marks Entry (14) and Faculty Attendance Entry (15) write into the **same canonical fact tables** that ETL loads (`student_subject_performance`, `daily_attendance_07`). ETL must **never** overwrite an existing operator-entered canonical fact. If an ETL source conflicts with a faculty-entered canonical value, the canonical/operator-entered value remains **authoritative** unless an explicit reconciliation/import operation is intentionally performed and audited (`01` §9).
- Together they make every value in the warehouse attributable: operator-entered facts trace to a change-log entry; ETL-derived values trace to a run manifest + pipeline version.
- `risk_predictions` rows reference the model version that produced them (`plan/03` §7.1) — the prediction-side lineage, consistent with the same ledger concept.

### 5.3 Source-to-Warehouse Lineage Rule

Every loaded row carries (implicitly via the ledger) `source → pipeline version → run → natural key`. Derived/gold rows additionally record which fact rows and which formulas produced them (`01` §3.1 stage outputs). This makes any gold number reducible to canonical facts and any canonical fact reducible to a source row — the auditability the blueprint demands.

---

## 6. Refresh and Operations

### 6.1 Batch Cadence (Locked)

Academic data is batch (`plan/03` §11.3); ETL runs are invoked explicitly (CLI, `01` §5–§6) in V1, with freshness watermark rather than scheduled automation. A future phase may add a schedule (Airflow/Prefect as escalation, `01` §5.4) — not V1.

### 6.2 Freshness Contract

- Every derived/gold consumer shows a freshness indicator ("last updated" from the watermark).
- ETL never blocks a dashboard; consumers read the last-known canonical state (P4).
- The request-path BFF cache (60s TTL, master status) is orthogonal to data-layer freshness and unchanged.

### 6.3 Idempotent, Safe Rerun

- Loads upsert on natural keys; derives are full recomputes of their grain within the run's transaction (`01` §6.1).
- A failed run leaves no partial canonical state (rollback); a re-run converges (P3).
- `--dry-run` reports exactly what would load/derive with no writes (`01` §5.3).

---

## 7. ETL-Maintained Derived-Field Matrix

These fields are **derived by ETL (batch) / by the write path (plans 14/15, incremental)** — never client-supplied, never hand-maintained. This matrix is the contract that keeps one source of truth per metric.

**Derive readiness gate (locked):** final academic values — SGPA, semester result, credits earned, pass/fail, and final percentage — are derived **only when the required academic facts for that term are complete**. Semester-7 performance data is incomplete today (marks partial, `result_status` NULL), so Semester-7 derived values must remain in a **clearly defined partial/NULL state** until the required facts are available. Missing final marks are **never** treated as zero. Seed-verified numbers below (e.g., STU000001 sem-7 = 7.84) are the **as-of snapshot** from seed, not recomputed-from-incomplete-sem-7 values; ETL reproduces them only once the underlying facts are complete.

| Table | Derived field(s) | Derivation (locked) |
|---|---|---|
| `students` | `full_name` | `first_name + ' ' + last_name` (name assembly) |
| `students` | `overall_attendance_percentage` | mean of aggregate `attendance_percentage` across all terms (verified: STU000001 = 79.78) |
| `students` | `latest_sgpa` | SGPA of the most recent **complete** term in `student_semester_summary` (verified: STU000001 sem-7 = 7.84 — as-of snapshot; only reproduced when sem-7 facts are complete) |
| `students` | `overall_cgpa` | cumulative across complete terms (verified: STU000001 = 7.83) |
| `students` | `overall_percentage` | cumulative percentage across complete terms |
| `students` | `total_credits_registered` / `total_credits_earned` | sum across `student_semester_summary`; earned only from complete/confirmed results — never assumed from missing marks |
| `students` | `total_backlogs` | count of failed subjects (verified: STU000032 = 24) |
| `students` | `academic_standing` | band from CGPA via Threshold Engine; partial/NULL when the underlying CGPA is not final |
| `attendance` (aggregate) | `total_classes`, `attended_classes`, `attendance_percentage` | from `daily_attendance_07` via plan-15 formulas (`02` §3.1) |
| `attendance` | `attendance_status`, `eligibility_status`, `shortage_flag`, `remarks` | from bands (config) |
| `student_semester_summary` | all aggregate columns | from `student_subject_performance` (+ `attendance` for attendance %); **never independently maintained** (`plan/03` §5.4); Semester-7 summary stays partial/NULL until marks are complete |

**Compatibility rule:** ETL updates these fields in place by their existing semantics (seed-verified formulas) and never changes their schema. All Faculty/Student/analytics queries that read them keep working unchanged (`01` §9).

---

## 8. Existing Database Compatibility

| Requirement | How satisfied |
|---|---|
| 16 live tables unchanged | ETL loads into the existing schema; V1 adds no staging table (`01` §7.2) |
| `daily_attendance_07` / `weekly_timetable_07` | Used as canonical load targets; their 0-byte migration stubs are acknowledged and must be replaced by proper DDL **in the implementation phase**, not by these docs |
| Seeded semester-1 aggregate `attendance` | Preserved untouched; sem-7 aggregate is newly derived (`02` §7) |
| Seeded `student_semester_summary` (sem 1–5) | Preserved as as-of snapshot; gold refresh appends/derives the same formulas for new terms |
| Sem-7 `student_subject_performance` (partial marks) | Validated but never overridden; plan 14 is the operator path. Missing final marks are **never** treated as zero; Derive leaves Sem-7 summary values partial/NULL until marks are complete (§7 readiness gate) |
| Write-path precedence (plans 14/15) | Faculty Marks/Attendance writes and ETL share the same canonical fact tables; ETL never overwrites an operator-entered canonical fact — canonical/operator-entered values remain authoritative unless an explicit reconciliation/import operation is performed (`01` §9, `02` §3.2) |
| `risk_predictions` (80 rows) | Prediction outputs recorded with their producing version; untouched by ETL |
| RLS off / app-layer authz | Unchanged (`plan/02`, master status §17.5) — ETL runs under the service credential with the same access model |
| Multi-tenancy | Keys already carry the tenant dimension; ETL scoping by (department_code, semester_no, academic_year) (`plan/03` §8) |

---

## 9. Rollback and Verification

### 9.1 Rollback

- **Failed run:** transaction rollback (no partial state), then re-run (idempotent).
- **Completed run needing revert:** re-run the prior verified dataset/version (sources are fingerprint-versioned in the ledger), or restore via the as-of snapshot discipline — ETL never destructively rewrites history (P9).
- Derived/gold tables are fully reproducible from canonical facts, so a gold-layer correction is always a re-derive, never an edit.

### 9.2 Verification Gates (per run)

| Gate | Check |
|---|---|
| Count reconciliation | loaded rows == expected (source-derived baseline, §3.2 rule); lecture counts 123; pairs 350; 50/lecture |
| Referential integrity | 0 orphans post-load; timetable uniqueness respected |
| Derived recompute | aggregate formulas reproduce seed-verified numbers (STU000001 81.11 / 79.78) for overlap terms |
| Manifest review | quarantine/review counts within configured ratio; exit code 0 |
| Read-path smoke | Faculty/Student analytics queries return without error on the refreshed state (no rewrite of queries) |

---

## 10. Future Extensibility and ML/GenAI Readiness

### 10.1 Multi-Semester / Multi-Source

- New semesters/departments: data + config, no code change (scoping keys in §8).
- New sources: add Extract/Validate adapters; Stitch/Transform/Load/Derive unchanged because they key on canonical identities (`02` §2).
- Real staging tables and a scheduled orchestrator are documented future options (Airflow/Prefect escalation, `01` §5.4) — **not** V1.
- Kafka/Redis/microservices: documented escalation only if a future streaming/cross-service requirement appears.

### 10.2 ML/GenAI Readiness

- **Features:** canonical student-grain facts + gold derived tables are the training surface; reproducible from facts (P2/P5) — the precondition for auditable features.
- **Prediction lineage:** `risk_predictions` records model version per row (`plan/03` §7.1); the lineage ledger gives feature-set provenance.
- **Isolation:** training is offline batch; serving is lightweight; a slow/failed retraining never blocks serving (blueprint §14) — the P4 principle extended to ML.
- **GenAI grounding:** `genai_insights` must be reproducible from structured source context (`plan/03` §7.2); the lineage/audit ledger is what proves grounding.
- **Explainability:** deterministic, versioned features feed tree-based models (XGBoost) whose SHAP values are answerable — impossible without the reproducible pipeline this document specifies.

---

## 11. Relationship to Other Plan Files

- `plan/03` §11 — the authority on validation/audit/refresh; this document implements its expectations without schema change.
- `plan/06` — quality gates (validate before load, quarantine, lineage) satisfied here.
- `plan/data_engineering/01` — the pipeline stages and execution model that this document's checks plug into.
- `plan/data_engineering/02` — the identity/stitch rules that feed the reconciliation and quarantine design.
- `plan/faculty/14`, `plan/faculty/15` — the operator-write audit trails this document's lineage ledger complements.
- `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` §11, §13–15 — the source of the batch/freshness/ML/GenAI expectations.
