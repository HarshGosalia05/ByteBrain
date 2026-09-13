# Data Engineering — Data Stitching and Identity Resolution

**Status:** Approved & Locked

**Version:** V1.0

**Module:** Data Engineering → Identity Resolution & Data Stitching

**Architecture:** Stitch-first, review-aware — canonical `Student_ID` as the universal key, explicit conflict handling, bridge tables versioned by semester/term

**Depends On:** `plan/data_engineering/01_reusable_etl_architecture.md` (pipeline stages), `plan/03` §3, §10 (canonical identity rules), `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` §12 (identity resolution), plans `14` (Marks Entry) and `15` (Attendance Entry), live schema (16 tables)

## 0. Position in the Project

This is the second of three Data Engineering planning documents. It is a **design specification only** — no code, no schema change, no implementation. It defines the identity model that makes the seven-stage ETL pipeline (document `01`) trustworthy: how every incoming record resolves to a canonical student/subject/faculty identity, how attendance and marks are stitched, and how the timetable/enrollment/subject/faculty relationship graph is kept correct.

The platform's trust model depends on this stage (`plan/03` §10.1): "The platform depends on combining academic, attendance, lifestyle, and career data into one coherent student view. If identity resolution is wrong, the system may produce analytics and predictions that look plausible but are silently incorrect." Stitching is called out separately from general ETL because it is the specific technical risk the whole platform depends on getting right (blueprint §12).

**V1 scope is locked:** Semester 7, CSE, 2026-27, subjects SUB0050–SUB0056, students STU000001–STU000050 (350 enrollment rows), datasets `daily_attendance_cse_sem7.csv` (6,150 rows / 123 lectures) and `weekly_timetable_cse_sem7.csv` (15 rows). All rules are keyed on canonical identifiers, so other semesters/departments are data additions, not rule changes.

---

## 1. Canonical Identity

### 1.1 The Two Academic Identifiers (Never Collapsed)

`plan/03` §3.3 is authoritative and locked:

- **`Student_ID`** (`STU######`) — the stable student stitching key used to relate the same person across all fact sets. This is the canonical person identity.
- **`Enrollment_No`** (`2023010001` CSE / `2023020030` BBA) — the repeated academic number preserved in the SQL fact rows. It is an academic numbering label, not a substitute for identity.

**Rule:** never collapse the two into a single term in the plan folder; never treat `Enrollment_No` as the canonical stitch key. `Enrollment_No` is carried alongside `Student_ID` in fact tables for academic-number fidelity only (`plan/03` §3.2).

### 1.2 Other Canonical Keys

| Key | Format | Owned by | Role |
|---|---|---|---|
| `Student_ID` | `STU######` | `students` | Person identity — universal stitch key |
| `Enrollment_No` | `2023######` | `students` (and fact tables) | Repeated academic number |
| `University_Roll_No` | `VARCHAR` | `students` | Secondary person identifier (future sources may carry it) |
| `Subject_ID` | `SUB####` | `subjects` | Subject identity |
| `Faculty_ID` | `FAC###` | `faculty` | Faculty identity (also `faculty_code`) |
| `Department_Code` | `INT` (1 = CSE) | `departments` | Department identity (`dept_code`) |
| `Enrollment_Record_ID` | `ENR######` | `student_subject_enrollment` | The (student, subject, semester) instance key — the fact-grain anchor |

### 1.3 Key Hierarchy in the Fact Grain

One `student_subject_enrollment` row = one (student, subject, semester_no, academic_year) instance. This is the **grain anchor** for both `student_subject_performance` (`PER######`) and aggregate `attendance` (`ATT######`) — the ENR–PER–ATT 1:1:1 alignment verified in the seed (`plan/03` master status §6.3). Stitching is correct when every fact row resolves to exactly one enrollment record.

---

## 2. Source-by-Source Identity Strategy

| Source | Native keys present | Stitch strategy |
|---|---|---|
| `students` (live table, seed `03_students_data.sql`) | `Student_ID`, `Enrollment_No`, `University_Roll_No`, `Department_Code` | The **person truth**. Every other source resolves *to* this table. No fuzzy matching is ever needed against it — V1 sources carry the canonical key directly. |
| `daily_attendance_cse_sem7.csv` (6,150 rows) | `student_id`, `enrollment_no`, `subject_id`, `subject_name`, `faculty_id`, `department_code`, `semester_no`, `academic_year` | **Self-keyed on all canonical keys.** Validate each against the masters: student must exist in `students`, subject in `subjects`, faculty in `faculty`, and the (subject, faculty, day, slot) must match `weekly_timetable_07`. `subject_name` is enriched from `subjects`, never trusted as identity. |
| `weekly_timetable_cse_sem7.csv` (15 rows) | `timttable_id` (typo in header, canonical col `timetable_id`), `department_code`, `semester_no`, `academic_year`, `day_name`, `slot_no`, `subject_id`, `subject_name`, `faculty_id`, `lecture_type` | **Subject/faculty-keyed, no student grain.** Validated against `subjects` (FK), `faculty` (FK), `departments` (FK) and the live `unique_timetable_slot` constraint `(department_code, semester_no, academic_year, day_name, slot_no)` — verified 15 rows, 0 orphans, 0 duplicates (`03` §3). |
| `student_subject_performance` (sem-7: 350 rows) | `performance_id`, `enrollment_record_id`, `enrollment_no`, `student_id`, `subject_id`, `semester_no` | **Stitch anchor alignment.** Resolves through `enrollment_record_id` → `ENR######` → the enrollment row; validates student/subject/semester against masters. Sem-7 rows today are partial (marks `NULL`, only `internal`/`mid_sem` populated, `result_status NULL`) — plan 14 fills them; ETL never overrides operator-entered values. |
| `student_semester_summary` (seeded `06_...sql`) | `semester_summary_id`, `student_id`, `enrollment_no`, `semester_no` | **Derived table** — never an input. ETL derives it (§6); existing seed rows for semesters 1–5 remain as the as-of snapshot. |
| Future sources (surveys, career forms, external exports) | May lack `Student_ID` (e.g., email / roll-number only) | Require an explicit mapping step (§5.2) with logged confidence — never silent fuzzy match (blueprint §12). |

### 2.1 `daily_attendance_07` Column Map

The CSV header (13 columns) maps to the live `daily_attendance_07` table exactly: `attendance_id, student_id, enrollment_no, subject_id, subject_name, faculty_id, lecture_date, lecture_number, day_name, department_code, semester_no, academic_year, attendance_status`. `attendance_status` domain is `P`/`A` (verified: P=5,379, A=771 across 6,150 rows).

**Two distinct keys — never conflated:**

- **Lecture session key** = `(subject_id, lecture_date, lecture_number)`. Identifies the lecture session. Used for **duplicate-lecture detection** and the `total_classes` derive (plan 15 §6.2). It is **not** the unique key for individual student attendance rows.
- **Individual attendance-row key** = `(student_id, subject_id, lecture_date, lecture_number)`. Uniquely identifies one student's attendance row for a lecture session. Used as the natural key for idempotent row loads/corrections (`01` §3.1).

---

## 3. Attendance and Marks Stitching

### 3.1 Daily Attendance → Aggregate Attendance

The live aggregate `attendance` table holds **one row per (student, subject, semester)** — the enrollment grain (plan 11 §6: "no per-session attendance in the schema"; plan 15 §6.2). ETL derives it from `daily_attendance_07` using the **locked plan-15 formulas**:

- `total_classes` = count of distinct `(lecture_date, lecture_number)` for that subject (shared by all students in scope).
- `attended_classes` = count of rows with `attendance_status = 'P'` for that student + subject.
- `attendance_percentage` = `attended / total × 100`.
- `attendance_status`, `eligibility_status`, `shortage_flag` from Threshold Engine bands (config: 75.0 / 60.0 / 90.0; Eligible ≥ 75, Critical < 60, Excellent ≥ 90; shortage = < 75).
- Matches verified seed math: STU000001 sem-7 avg = 81.11, overall mean across 56 attendance rows = 79.78 = `students.overall_attendance_percentage` (plan 15 §6.4).

**Reconciliation reality (V1):** the seeded aggregate `attendance` covers **semester 1** (90 classes per subject, subjects SUB0001–…). The sem-7 daily dataset (123 lectures) has **no seeded aggregate** — ETL's derive stage creates sem-7 aggregate rows from daily facts. It must **not** delete or rewrite the sem-1 seeded rows (P9 history preservation; plan-15 write path owns incremental updates).

### 3.2 Marks Stitching

`student_subject_performance` rows resolve via `enrollment_record_id` to their enrollment (student + subject + semester). Marks are stitched at the (student, subject, semester) grain. ETL's role for marks:

- **Validate** that each performance row references an existing enrollment with matching student/subject/semester (no orphans, `03` §3).
- **Never override** marks entered through plan 14 (canonical table is the source of truth). Faculty Marks Entry (14) and ETL operate on the **same canonical fact table**; ETL must **never** overwrite an existing operator-entered canonical fact. If an ETL source conflicts with a faculty-entered canonical value, the canonical/operator-entered value remains **authoritative** unless an explicit reconciliation/import operation is intentionally performed.
- **Partial marks protection:** Semester-7 performance rows are incomplete today (`internal`/`mid_sem` populated, `end_sem`/`total`/`percentage`/`grade`/`result_status` NULL). Derive must **not** fabricate final values from incomplete marks — final SGPA, semester result, credits earned, pass/fail, and final percentage are derived **only when the required academic facts are complete**; incomplete terms remain partial/NULL, and missing final marks are **never** treated as zero.
- **Feed derive:** `student_semester_summary` aggregates (subjects_registered, credits, totals, SGPA, semester_result) come from `Subject_Performance` (+ `Attendance` for the attendance percentage) — the two-source-of-truth rule (`plan/03` §5.4, P5), subject to the readiness gate above.

### 3.3 Stitch-Key Resolution Order (Per Fact Row)

1. Resolve `enrollment_record_id` → `ENR######` → `student_subject_enrollment`.
2. Verify `student_id` ↔ `students`, `subject_id` ↔ `subjects`, `semester_no` matches the enrollment.
3. For daily attendance additionally verify `faculty_id` ↔ `faculty` and timetable slot membership.
4. Only a fully-resolved row proceeds to Transform/Load; anything else routes to quarantine/review (§5).

---

## 4. Timetable / Enrollment / Subject / Faculty Relationship Graph

### 4.1 The Graph

```
departments (dept_code)
   ├── students (department_code)          ── 1:N
   ├── faculty (department_code)           ── 1:N
   └── subjects? (via department context)
faculty (faculty_id) ──┐
subjects (subject_id) ──┼── weekly_timetable_07 (subject_id, faculty_id, day, slot)   [15 rows, verified]
                       └── student_subject_enrollment (faculty_id, subject_id, semester)  [350 sem-7 rows]
student_subject_enrollment ── student_subject_performance (enrollment_record_id)          [350 sem-7]
                          ── attendance (enrollment_record_id)                           [3,850 seeded]
daily_attendance_07 (student_id, subject_id, faculty_id, date, lecture_number)            [6,150 rows]
```

### 4.2 Verification Grounding

The live timetable was verified (`backend/analysis/verification_results.json`): 14 columns, PK `timetable_id` (bigint), FKs to `departments.dept_code`, `faculty.faculty_id`, `subjects.subject_id`, unique constraint `unique_timetable_slot` on `(department_code, semester_no, academic_year, day_name, slot_no)`, 15 rows, 0 nulls, 0 orphans, 0 duplicate slots, sequence next_val 17. `attendance_analysis.json` mirrors the timetable with `lecture_type` (Theory/Lab) and gives the weekly lecture-frequency map (SUB0050=3, SUB0051=2, SUB0052=1, SUB0053=3, SUB0054=2, SUB0055=2, SUB0056=2). These verified facts are the relationship contract ETL validates against.

### 4.3 Lecture Session Key and Duplicate Detection

The **lecture session key** is `(subject_id, lecture_date, lecture_number)`. Plan 15 §6.2 uses it for duplicate detection (a recorded set = correction, a new set = insert). ETL uses the session key for duplicate-lecture detection and the `total_classes` derive. Individual student attendance rows are uniquely identified by the **attendance-row key** `(student_id, subject_id, lecture_date, lecture_number)`; idempotent loads/corrections upsert on that row key (`01` §3.1). A lecture appearing twice for the same subject+date+number is a **data-quality violation** (quarantine or fail-loud) — it would silently inflate `total_classes`.

---

## 5. Conflict, Ambiguity, and Review

### 5.1 Locked Identity Rules (plan/03 §10.2, blueprint §12)

- `Student_ID` is canonical; mapping to it happens during staging/stitching, never after load.
- Sources without native `Student_ID` require an explicit mapping step with a logged confidence/method.
- **Never** silent fuzzy matching as the default for identity-critical records.
- **Never** drop ambiguous records without traceability.
- **Never** overwrite relationship history when a new term/mapping appears.
- Ambiguous or unmatched records route to a **review queue** (data loss and mismatch are both worse than a delayed record).

### 5.2 Mapping Steps (Future Sources)

For a future survey keyed by `email` or `university_roll_no`:

1. Exact match on `University_Roll_No` / `email` against `students` → confidence `exact`.
2. Exact match on `Enrollment_No` → confidence `exact` (academic-number fidelity, but the record is still written under `Student_ID`).
3. No exact match → **review queue**, not fuzzy fallback.
4. Method + confidence logged per record into the lineage ledger (`03` §5).

### 5.3 What Is NOT a Conflict in V1

V1 sources are all self-keyed on canonical identifiers. The common failure modes are therefore **validation** (unknown subject/faculty/student, malformed date, bad status) rather than identity inference. These go to quarantine (`03` §4). The review-queue machinery is specified now because multi-source extensibility (§8) will introduce genuine ambiguity; it is not exercised by V1 data.

---

## 6. Bridge Tables — Historical Versioning

Two first-class stitching artifacts (`plan/03` §10.3, blueprint §12):

- **`student_subject_enrollment`** — resolves Students ↔ Subjects across semesters; must stay historically queryable even after reassignment. `enrollment_status` ('Active' / others) and `enrollment_date` version the term.
- **`faculty_student_map`** — resolves the mentor/advisor relationship; versioned by semester/term (seed `10_faculty_student_map_data.sql`, 1:1 with students in the seed).

**ETL rule:** load/derive never rewrites history. New term data adds rows; changed relationships add rows with the new term context rather than mutating prior rows (P9). The ENR–PER–ATT 1:1:1 seed alignment is the invariant to preserve on every run.

---

## 7. Reconciliation — Daily Facts vs Seeded Aggregates

| Item | Daily / lecture-level | Aggregate `attendance` |
|---|---|---|
| Source | `daily_attendance_07` (6,150 rows, 123 lectures, sem-7 CSE 2026-27) | Seeded `13_attendance_data.sql` (3,850 rows, one per enrollment, all seeded terms) |
| Grain | (student, subject, lecture_date, lecture_number) | (student, subject, semester) — enrollment grain |
| Sem-7 coverage | Full (all 123 lectures for SUB0050–56) | **None** — seeded rows are semester 1 (90 classes) and other terms |
| Derive | → aggregate via plan-15 formulas | Read-only for analytics (plan 11/12); plan 15 recomputes on write |
| Stitch link | `student_id` + `subject_id` + `faculty_id` | `enrollment_record_id` → enrollment |

**Locked reconciliation outcome:** sem-7 aggregate attendance is **derived from daily attendance by ETL** (and maintained incrementally by plan 15 on write). Seeded aggregate rows for earlier terms are **preserved untouched** as the as-of snapshot. This satisfies the two-sources-of-truth rule: `daily_attendance_07` is the canonical lecture record; the aggregate table is derived, never independently maintained.

---

## 8. Validation Rules That Protect Stitching

Applied in the Validate/Stitch stages (`01` §3); exact thresholds/expectations in `03` §3:

1. `student_id` exists in `students`; `enrollment_no` consistent between CSV and `students`.
2. `subject_id` exists in `subjects`; `subject_name` in CSV agrees with `subjects` (mismatch → quarantine, not rename).
3. `faculty_id` exists in `faculty` and the subject→faculty assignment matches the timetable for that day+slot.
4. **Lecture session key** `(subject_id, lecture_date, lecture_number)` unique in the load scope (no duplicate lectures). Individual student rows are then uniquely keyed by the **attendance-row key** `(student_id, subject_id, lecture_date, lecture_number)`.
5. `attendance_status` ∈ {P, A}.
6. `department_code`/`semester_no`/`academic_year` consistent with the run scope.
7. Performance rows resolve to an enrollment with matching (student, subject, semester).
8. 50 students per lecture expected (350 pairs across 7 subjects — verified).

---

## 9. Observability of Stitch Results

Every run reports, per source, into the lineage ledger (`03` §5):

- rows in → rows stitched → rows to load → rows quarantined → rows to review.
- counts per stitch key (distinct `Student_ID`, `Subject_ID`, `Faculty_ID`, `Enrollment_Record_ID`).
- unresolved/ambiguous records with their reason (the review queue).
- mismatch details (subject_name, faculty assignment, duplicate lectures).

These counts make a failed or suspicious run visible immediately (P1 fail-loud, `03` §9) rather than silently corrupting downstream analytics or predictions.

---

## 10. Relationship to Other Plan Files

- `plan/03` §3, §10 — canonical identity and stitching integrity rules; this document operationalizes them.
- `plan/data_engineering/01` — the pipeline stages; Stitch is stage four, with the review-queue and quarantine contracts defined here.
- `plan/data_engineering/03` — the validation/reconciliation matrix, quarantine design, and lineage ledger that record stitch outcomes.
- `plan/faculty/15` — the write path that shares the daily-attendance→aggregate formulas and the duplicate-lecture key.
- `plan/faculty/14` — the marks write path whose canonical rows ETL validates but never overrides.
- `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` §12 — the authoritative identity-resolution rules.
