# Data Engineering — Reusable ETL Pipeline Architecture

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Data Engineering → Reusable ETL Architecture

**Architecture:** Design-first, reuse-first — lightweight deterministic batch pipeline inside the FastAPI service (no Airflow / Prefect / Kafka / Redis / microservices in V1)

**Depends On:** `plan/00` (glossary, canonical terminology), `plan/02` (service boundaries), `plan/03` (schema + ETL owning document), `plan/06` (delivery/quality), `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` §11–12, `backend/app/core/config.py` (Threshold Engine), `backend/app/core/database.py` (asyncpg pool), plans `14` (Marks Entry) and `15` (Attendance Entry)

## 0. Position in the Project

This is the first of three Data Engineering planning documents (folder `plan/data_engineering/`):

- `01_reusable_etl_architecture.md` — this file: the reusable ETL pipeline (stages, components, orchestration, execution).
- `02_data_stitching_and_identity_resolution.md` — the canonical `Student_ID` identity model, attendance/marks stitching, and the timetable/enrollment/subject/faculty relationship graph.
- `03_data_quality_warehouse_and_operations.md` — warehouse layers (staging / canonical / gold), data quality and quarantine, lineage, auditability, refresh, and operations.

These documents are **design specifications only**. They introduce no code, no schema change, no migration, and no pipeline implementation. The ETL phase ends when the three planning documents exist and are verified. Implementation is a separate, later phase that will cite these documents as its build specification.

The platform today is **read-only for academic facts** and has **zero ETL code** (master status §6.4: "Design-only; zero ETL code"). The `daily_attendance_07` (6,150 rows) and `weekly_timetable_07` (15 rows) tables exist live but are not referenced by any backend code, and their migration stubs (`10_weekly_timetable_07.sql`, `11_daily_attendance_07.sql`) are empty. Plan 15 makes `daily_attendance_07` the canonical write path for lecture-level attendance. The ETL pipeline in this document is the **batch twin** of that write path: the same recompute formulas, the same thresholds, the same two-sources-of-truth discipline, executed deterministically over whole datasets instead of a single lecture transaction.

**V1 scope is locked:** Semester 7, CSE, 2026-27, subjects SUB0050–SUB0056, students STU000001–STU000050 (350 enrollment rows), source datasets `backend/datasets/daily_attendance_cse_sem7.csv` (6,150 rows, 123 lectures) and `backend/datasets/weekly_timetable_cse_sem7.csv` (15 rows). Everything is scoped by configuration and database relationships — never hardcoded — so BBA and other semesters, and future source systems, become a configuration/data exercise (see §10).

---

## 1. Purpose and Scope

### 1.1 What This Document Defines

- The seven-stage ETL pipeline: **Extract → Validate → Stage → Stitch → Transform → Load → Derive**.
- The reusable components that already exist and must be composed, and the components that are missing and must be built.
- The V1 orchestration decision and its justification (lightweight and deterministic; no scheduler infrastructure).
- The execution model: rerunnable, idempotent, auditable, fail-loud.
- The refresh discipline and freshness contract for downstream consumers.
- The relation of ETL to the Faculty Marks Entry (14) and Attendance Entry (15) write paths.
- The future escalation path (Airflow / Prefect) and ML/GenAI readiness, documented but **not** adopted in V1.

### 1.2 What This Document Does NOT Define

- The `Student_ID` identity resolution rules — owned by `02_data_stitching_and_identity_resolution.md`.
- The validation rules, quarantine schema, and reconciliation numbers — owned by `03_data_quality_warehouse_and_operations.md`.
- The predictive model pipeline (training, serving, model registry) — owned by `plan/04` and future ML plans.

### 1.3 Non-Goals of the ETL Phase (Locked)

- **No** Airflow, Prefect, Kafka, Redis, or any new microservice in V1.
- **No** new tables, columns, indexes, or constraints beyond what the existing schema already provides (staging is a processing convention, see §7.2).
- **No** real-time streaming. ETL is explicitly batch and explicitly out of the request path of any user-facing API (blueprint §11).
- **No** rewrites of existing analytics queries. The 16 live tables and all Faculty/Student read paths remain the contract ETL loads into.

---

## 2. Locked Design Principles

| # | Principle | Meaning |
|---|---|---|
| P1 | **Fail loudly** | A failed ETL run must raise an explicit, structured error with a non-zero exit code and a log line. It must never silently skip rows or return "success" with partial data. (Blueprint §Reliability) |
| P2 | **Deterministic** | The same input data and configuration produce identical canonical and derived **business results** on every run, independent of row order or execution time. `run_id`, timestamps, logs, and other execution metadata may naturally differ between runs; they are never part of the business result. No randomness, no time-dependent aggregation windows (except explicit run timestamps written to lineage), no dependence on row order. |
| P3 | **Idempotent / rerunnable** | Re-running the pipeline after a completed or failed run converges to the same canonical state. Loads upsert on natural keys; derives are recomputed from facts, never appended twice. |
| P4 | **Batch, out of the request path** | ETL never blocks a dashboard load. Consumers see slightly stale but known data with a freshness indicator, never a live-pipeline dependency (blueprint §11, `plan/06`). |
| P5 | **Two-sources-of-truth prevention** | A metric is derived from exactly one fact source. `student_semester_summary` is populated by ETL from `Subject_Performance` + `Attendance` and is **never independently maintained** (`plan/03` §5.4). Raw facts stay raw; derived summaries are recomputed. |
| P6 | **Quarantine, never silently drop** | Any record failing validation is quarantined and logged with its reason. Identity-ambiguous records route to a review queue. No silent data loss (blueprint §11). |
| P7 | **Stitch before load** | Source systems map to `Student_ID` during staging/stitching, never after warehouse load (`plan/03` §3.2, §10.2). |
| P8 | **Auditable** | Every loaded row is traceable to its source, the pipeline version that produced it, and the run that wrote it. Prediction and insight outputs record their producing model/pipeline version (`plan/03` §11.2). |
| P9 | **Preserve history** | Academic facts keep semester history; overwriting old values is prohibited. Bridge tables (`student_subject_enrollment`, `faculty_student_map`) preserve relationship changes over time (`plan/03` §5.5, §10.3). |
| P10 | **Reuse-first** | Compose existing, verified pieces (Threshold Engine, plan-15 recompute formulas, asyncpg pool, existing schema) before building anything new. |

---

## 3. The Seven-Stage Pipeline

The blueprint's ETL flow (`plan/03` §9.1) is **Extract → Validate and stage → Stitch → Load → Derive**. This document expands it into seven explicit stages by splitting "Validate and stage" into **Validate** and **Stage**, and inserting **Transform** between **Stitch** and **Load** to make the semantic/format work a first-class, testable stage.

```
Source(s) ──> Extract ──> Validate ──> Stage ──> Stitch ──> Transform ──> Load ──> Derive
               │             │           │         │            │            │        │
               │        quarantine     staging    identity    mapping,     upsert   summary/
               │        on failure     bucket     resolution   derivation   to       gold
               │                                    │                        canonical   tables
               │                             review queue on
               │                             ambiguity
```

### 3.1 Stage Definitions

| Stage | Responsibility | Output |
|---|---|---|
| **Extract** | Pull raw source bytes/rows with their source identity preserved. No transformation. Sources: CSV datasets today; exam records, survey exports, career-preference forms tomorrow (`plan/03` §9.2). | Raw rows + source metadata (file, row, checksum). |
| **Validate** | Schema checks (column names/types present), integrity checks (required keys non-null), completeness checks (row counts vs expected), domain checks (P/A statuses, date formats). Failures → quarantine with reason. | Validated rows; quarantine log. |
| **Stage** | Place validated rows into a staging bucket keyed by (source, run_id). In this implementation staging is a **processing convention** — validated rows held in memory/on the staging path with run metadata — because no staging tables exist and V1 adds none (see §7.2). | Staged rows tagged with run_id. |
| **Stitch** | Resolve every row to canonical identity keys: `Student_ID`, `Enrollment_No`, `Subject_ID`, `Faculty_ID`, `enrollment_record_id`. Identity conflicts → review queue, never silent fuzzy match. Full rules in `02`. | Stitched rows on canonical keys. |
| **Transform** | Apply deterministic mappings and derivations at the fact grain: date parsing, code→name enrichment (subject_name, faculty assignment from timetable), lecture-session keys, aggregate computations that belong at load time are deferred to Derive — Transform is semantic normalization, not summarization. | Canonical-shaped rows. |
| **Load** | Upsert transformed rows into the canonical tables on natural keys, never duplicating, never overwriting history outside the defined upsert semantics. For `daily_attendance_07`, the **individual attendance-row key** is `(student_id, subject_id, lecture_date, lecture_number)`; the surrogate `attendance_id` is preserved for corrections. The **lecture session key** `(subject_id, lecture_date, lecture_number)` is *not* the unique key for individual student rows — it identifies the lecture session and is used for duplicate-lecture detection and `total_classes` only. Timetable rows load on `timetable_id`. | Canonical tables updated; load manifest. |
| **Derive** | Compute gold-level aggregate tables from the loaded canonical facts: aggregate `attendance` rows, `student_semester_summary`, and the ETL-maintained derived columns on `students` (§9, `03` §7). Same formulas as the plan-15 write path. **Readiness gate:** final derived values (SGPA, semester result, credits earned, pass/fail, final percentage) are produced only when the required academic facts for that term are complete; incomplete terms (e.g., Semester-7 marks are partial today) remain in a defined partial/NULL derived state and missing final marks are **never** treated as zero. | Gold tables refreshed; derivation manifest. |

### 3.2 Stage Invariants

- Every stage is a pure function of its input + configuration, so it is independently testable and rerunnable.
- Stages do not silently skip; they either pass a row forward or route it to quarantine/review with a reason.
- The run_id flows through every stage so a load can be traced to its entire provenance.

---

## 4. Component Inventory (Reusable vs Missing)

### 4.1 Reusable — Compose First

| Component | Location | Role in ETL |
|---|---|---|
| **Threshold Engine** | `backend/app/core/config.py` | Single source of truth for every band/eligibility/shortage/grade rule used in Transform and Derive. ETL reads the same constants the analytics and write paths use — no duplicated numbers. |
| **Plan-15 recompute formulas** | `plan/faculty/15_faculty_attendance_entry_module_plan.md` §6.2–6.4 | `total_classes = distinct (lecture_date, lecture_number)`; `attended_classes = count 'P'`; `attendance_percentage = attended/total×100`; semester/overall means. Verified against seed (STU000001: sem-7 81.11, overall 79.78). ETL reuses them verbatim. |
| **asyncpg pool** | `backend/app/core/database.py` | The database access layer ETL runs on (min_size 1, max_size 10, dsn from `settings.database_url`). |
| **CSV datasets** | `backend/datasets/*.csv` | The V1 source data: `daily_attendance_cse_sem7.csv` (6,150 rows, 123 lectures), `weekly_timetable_cse_sem7.csv` (15 rows). |
| **Canonical schema** | 16 live tables (4 groups) | The load target. `student_subject_enrollment` (350 sem-7 rows) is the stitch anchor; `subjects`/`faculty`/`departments` are the reference masters. |
| **Pydantic v2** | `backend/app/schemas/*` | Validation models for structured data; reusable pattern for ETL row validation. |
| **Structured logging** | uvicorn/logging in FastAPI | The logging substrate ETL run logs write to. |

### 4.2 Missing — Must Be Built (In the Future Implementation Phase)

| Gap | Impact | Documented |
|---|---|---|
| **Zero ETL code** | No extractor, validator, stitcher, or loaders exist. | This doc §5–§6. |
| **No `pandas` / orchestrator in `requirements.txt`** | Today: `fastapi`, `uvicorn[standard]`, `asyncpg`, `pydantic`, `pydantic-settings`, `PyJWT`. V1 ETL intentionally needs only the Python standard library (`csv`) + `asyncpg`; adding `pandas` is a future decision, not a V1 requirement. | This doc §5.3. |
| **Empty migration stubs** | `10_weekly_timetable_07.sql`, `11_daily_attendance_07.sql` are 0 B; `12_indexes.sql`, `13_constraints.sql` are 0 B. Tables exist live with verified structure but have no executable DDL. | `03` §8; must not be recreated from these docs. |
| **Audit change-log tables** | `performance_change_log` (14) and `attendance_change_log` (15) are planned-only, no DDL. ETL load/derive runs will write to a future `etl_run`/lineage ledger. | `03` §5. |
| **Analysis JSON staleness** | `backend/analysis/lecture_analysis.json` reports 107 lectures / 5,350 rows; the actual CSV has 123 lectures / 6,150 rows (SUB0055/56 = 16 each, not 8). | `03` §3 (reconciliation matrix). |

### 4.3 Reuse Discipline

- **No duplicated thresholds** — every number in Transform/Derive resolves to `config.py`.
- **No duplicated recompute logic** — the ETL derive stage and the plan-15 write path share one formulation, kept in sync by these documents.
- **No new database stack** — same Supabase PostgreSQL via `asyncpg` (FastAPI side) / `pg` (Next.js BFF side) as today; no REST, no RLS (deliberately off, `plan/02`, master status §17.5).

---

## 5. Orchestration Decision

### 5.1 The Decision (Locked for V1)

ETL is executed by a **lightweight, deterministic, rerunnable command-line runner** owned by the FastAPI service (a `backend` script invoked with `python -m <etl_package> <stage|run> [--source ...] [--dry-run]`). There is **no scheduler, no queue, no worker pool, no workflow engine** in V1.

The pipeline is a single process that walks the seven stages, writes a run manifest, and exits 0 on success / non-zero on failure. For the V1 data volume (6,150 daily rows, 15 timetable rows, 350 enrollments, 3850 aggregates), this completes in well under a minute — far below any batch-cadence pressure.

### 5.2 Justification (Why This Satisfies "Avoid Airflow Unless Justified")

| Constraint | How the lightweight runner satisfies it |
|---|---|
| Blueprint says "Airflow or Prefect schedules and monitors these stages, handles retries, and alerts on failure" (§11) | Airflow/Prefect are **scheduling + retry + alerting** concerns. V1 has no external schedule, manual triggering only; retries are the runner's own idempotent re-run (safe by P3); alerting is a structured error + non-zero exit consumed by the operator. The *stages themselves* are identical either way. |
| `plan/06` places ETL as module-order step 2 with quality gates | A single-process runner is the smallest correct implementation of those gates (validate → quarantine → load → derive → manifest). |
| Phase constraint: "avoid microservices / Airflow unless justified" | Justification absent for V1: no concurrency, no distributed sources, no wall-clock SLA, single tenant. Infrastructure cost and operational surface are not warranted at 6,150 rows. |
| Determinism + auditability (P2, P8) | A CLI gives exact, reproducible invocation (command line = configuration snapshot) and a per-run manifest — easier to audit than a scheduler's DAG state. |
| Compatibility with plans 14/15 | The write path is transactional per lecture; ETL is batch per dataset. Both call the same recompute formulation (§9). No scheduler relationship exists. |

### 5.3 V1 Runner Shape (Design Sketch — No Implementation)

- Entry: `python -m etl run --sources daily_attendance,weekly_timetable --dry-run|--apply`.
- Configuration: reuses `backend/app/core/config.py` settings; no new config system.
- Execution: one async process using the existing `asyncpg` pool; stages execute sequentially with per-stage result objects.
- Outputs: a per-run manifest (run_id, started/finished UTC, per-stage row counts, quarantine counts, load counts, derive counts, pipeline version, exit code), written to the lineage ledger (see `03` §5) and a run log.
- Safety: `--dry-run` executes Extract→Transform with validation and reports exactly what would load/derive, without writing; `--apply` is the only mode that touches the database.
- Exit codes: `0` success; `1` validation/quarantine-exceeds-threshold failure; `2` stitch ambiguity; `3` load/derive failure; each with a structured message.

### 5.4 Escalation Path (Future, Documented Only)

When a future phase introduces **scheduled cadence, multi-source concurrency, distributed retries, or operator alerting**, the same stages are wrapped by **Airflow (or Prefect)** as the scheduler/monitor. The stages remain the pure functions of §3.2, so the escalation is a wrapper, not a rewrite (mirrors blueprint §11 "Airflow or Prefect schedules and monitors"). Kafka/Redis are documented as escalation options only if a future requirement introduces streaming or cross-service queues — **not** needed for V1 batch.

---

## 6. Execution Model

### 6.1 Run Semantics

- **run_id**: generated once per invocation (UTC timestamp + short nonce); flows through every stage and every lineage record.
- **Freshness metadata**: each load/derive writes `last_etl_run_id` / `last_etl_updated_at` into the lineage ledger; BFF/UI freshness indicators read it (`plan/06`, master status BFF cache pattern).
- **Idempotence**: all loads are upserts on natural keys; all derives are full recomputes scoped to their grain (delete-and-rebuild of the derived grain within the run's transaction, never blind appends). A re-run of a failed run converges (§P3).

### 6.2 Failure Behavior

| Failure | Behavior |
|---|---|
| Validation failure (row-level) | Row → quarantine with reason; run continues; at end, if quarantined ratio exceeds `ETL_MAX_QUARANTINE_RATIO` (config), run exits 1 (fail loud) rather than "succeed with garbage". |
| Stitch ambiguity/unmatched | Identity record → review queue (never force-matched, never dropped); if unresolved, run exits 2. |
| Load/derive SQL error | Transaction rollback; run exits 3; no partial canonical state. |
| Missing/renamed source file | Extract fails; run exits 1 with a clear message. |

### 6.3 Logging

- Structured logs: one line per stage with run_id, stage, rows_in, rows_out, rows_quarantined, elapsed.
- A final summary log line with all counts and exit code.
- The run manifest is the audit artifact; logs are operational.

---

## 7. Refresh Discipline and Freshness

### 7.1 Batch, Not Real-Time (Locked)

Academic data is batch by nature (`plan/03` §11.3). Downstream consumers must expect **freshness indicators, not live mirroring**. The system must be resilient to slightly stale but known data.

### 7.2 Staging Convention (No New Tables)

V1 adds **no staging tables** to the 16-table schema. Staging is a processing convention:

- Validated/stitched rows live in memory with their run_id for the duration of the run.
- Only the canonical load and the derived gold writes touch the database.
- A future multi-source phase may introduce real staging tables; this is a documented future option, not a V1 schema change.

### 7.3 Freshness Contract

- Every derived/aggregate view is accompanied by a "last updated" indicator (the existing `FreshnessBadge` pattern / BFF cache TTL of 60s in the master status is for request-path caching; ETL freshness is the data-layer watermark).
- A dashboard never waits on ETL; it reads the last-known canonical state with its watermark.

---

## 8. Multi-Tenancy Readiness

`plan/03` §8 requires tenant compatibility without acting as a SaaS today. ETL applies this discipline:

- Every stage carries the tenant dimension implicitly through the canonical keys (department_code / student / faculty records already carry the identifiers that support tenancy).
- ETL runs are scoped by (department_code, semester_no, academic_year) — the natural partition for V1 — and never assume a single global table identity.
- No ETL design decision hardcodes CSE/sem-7; tenant/semester scoping comes from configuration and the data itself.

---

## 9. Relation to Faculty Marks Entry (14) and Attendance Entry (15)

The ETL pipeline and the write-path modules are the **two halves of one recompute discipline**:

| Aspect | Write path (plans 14/15) | ETL batch (this doc) |
|---|---|---|
| Trigger | Faculty transaction (single lecture / single mark row) | Whole-dataset run (CLI) |
| Grain | One (student, subject, lecture) / one (student, subject) | Same grains, full scope |
| Recompute | Transactional recompute of affected aggregates (§15 §6.2–6.4) | Derive stage, full-scope recompute |
| Formulas | `total_classes` / `attended_classes` / `percentage`, semester/overall means | Identical formulas (§3.1, §4.1) |
| Audit | `attendance_change_log` / `performance_change_log` (planned) | Run manifest + lineage ledger (future) |
| Source of truth | `daily_attendance_07` becomes canonical write source (15) | Reads the same canonical tables; never bypasses them. **Write-path precedence:** plans 14/15 and ETL operate on the *same* canonical fact tables (`student_subject_performance`, `daily_attendance_07`); ETL never overwrites an existing operator-entered canonical fact. If an ETL source conflicts with a faculty-entered canonical value, the canonical/operator-entered value remains authoritative unless an explicit reconciliation/import operation is intentionally performed. |

**Contract:** ETL never rewrites analytics queries, never bypasses the write path's tables, and never introduces a second attendance or performance truth (P5). **Faculty Marks Entry (14) and Faculty Attendance Entry (15) write into the same canonical fact tables that ETL loads** — `student_subject_performance` (plan 14) and `daily_attendance_07` (plan 15). ETL must **never** overwrite an existing operator-entered canonical fact. If an ETL source conflicts with an existing faculty-entered canonical fact, the canonical/operator-entered value remains **authoritative** unless an explicit reconciliation/import operation is intentionally executed; such operations are deliberately invoked and audited, never implicit in a normal ETL run. This preserves the plans 14/15 write-path contract. The seeded aggregate `attendance` rows for semester 1 remain untouched; the sem-7 aggregate is derived from `daily_attendance_07` (see `02` §7).

---

## 10. Future Extensibility

### 10.1 Multi-Semester and Multi-Source

- Every stage is scoped by (department_code, semester_no, academic_year) from configuration/data — BBA, additional semesters, and new CSE sections are data additions, not code changes.
- New source systems (exam office exports, survey/forms, career-preference forms) plug in as **new Extract + Validate adapters**; the Stitch/Transform/Load/Derive stages are unchanged because they key on canonical identities.
- Sources lacking native `Student_ID` (e.g., email/roll-number-only surveys) require the explicit mapping stage defined in `02` §5.

### 10.2 ML/GenAI Readiness

- **Feature-ready facts:** the canonical student-grain model (`plan/03` §3.1) and the derived gold tables are the training/feature surface; the pipeline guarantees they are reproducible from facts (P2, P5), which is the precondition for auditable model features.
- **Versioning:** `Risk_Predictions` records the model version that produced each prediction (`plan/03` §7.1); the run manifest/pipeline version gives feature-set provenance.
- **Decoupling:** training is an offline batch job, serving is a lightweight API, and "a slow or failed retraining run must never block serving" (blueprint §14) — the same isolation principle as P4. The ETL derive stage is the shared upstream of both training features and dashboard aggregates.
- **GenAI grounding:** `GenAI_Insights` must be grounded in structured source context (`plan/03` §7.2, blueprint §15); the lineage/audit ledger (this doc + `03` §5) is what makes that grounding provable.
- **Explainability:** deterministic, auditable features from ETL feed tree-based models (XGBoost) where SHAP values can explain decisions — only possible if features are reproducible and versioned.

---

## 11. Relationship to Other Plan Files

- `plan/00` — glossary and canonical terminology; ETL uses the same language (no analytics/risk/GenAI terms for data-movement operations).
- `plan/02` — service boundaries; ETL lives in the FastAPI (Intelligence & Data Layer) side, never in Next.js.
- `plan/03` — the authority on schema and ETL behavior; this document operationalizes its §9 stages and its §11 quality/audit expectations.
- `plan/06` — ETL is module-order step 2; this document satisfies its quality gates (validate before load, quarantine, lineage).
- `plan/04` — analytics/ML/GenAI engine; §10.2 aligns feature/version readiness with that document.
- `plan/faculty/14`, `plan/faculty/15` — the write-path twins of §9.
- `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` §11–12 — the authoritative source this document implements without adding new infrastructure.
