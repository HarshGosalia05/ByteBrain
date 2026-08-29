# ByteBrain — ML Data Correction Specification (Record-by-Record)

**Spec ID:** `ML-CORRECTION-SPEC-2026-08-29`
**Companion to:** `plan_25_08/ml_complete_data_forensic_audit_report.md`
**Auditor discipline:** STRICT READ-ONLY. This document is the **specification only**. It does NOT execute any correction. Every proposed value was verified against authoritative live-DB / CSV evidence captured read-only; all new derivations in this spec were recomputed in temp (`C:\Users\HARSHG~1\AppData\Local\Temp\opencode\`).
**Authoritative-data principle:** live subject-level marks/attendance > completed-semester summary derived from valid subject records > DB-derived fields > CSV only where verified > seed ONLY as evidence of seeding > ML predictions NEVER authoritative.
**Hard invariant:** CSE Sem-7 (and BBA Sem-5) are incomplete → actual SGPA/percentage/grade/result/backlog/credits-earned = **NULL** unless independently derivable; M2/M3 predicted SGPA must NEVER become actual SGPA.
**Do not execute.** Deliverable is the correction specification, not the correction.

---

## SECTION 1 — MASTER ISSUE REGISTER

Classification vocab: `ACTUAL` `DERIVED` `PREDICTED` `SEEDED` `PLACEHOLDER` `MISSING` `CONTRADICTORY` `INVALID` `UNKNOWN`.
Correction method vocab: `DERIVE_FROM_AUTHORITATIVE_DATA` `SET_TO_NULL` `REMOVE_FROM_TRAINING` `PRESERVE` `MANUAL_REVIEW` `NO_ACTION`.

| Issue_ID | Severity | Source | Table/File | Record_ID | Student | Sem | Field | Current_Value | Classification | Evidence | Problem | Authoritative_Source | Proposed_Value | Correction_Method | Confidence | Manual_Review | Downstream_Impact |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ISS-001 | CRITICAL | Live DB migration seed | students.latest_sgpa | all 80 student rows | ALL (CSE 50+BBA 30) | — | latest_sgpa | CSV-fabricated Sem7 (CSE) / Sem5 (BBA) SGPA | =Sem7 CSV sgpa 50/50 CSE; =Sem5 CSV sgpa 30/30 BBA (recomputed) | SEEDED placeholder of an incomplete live semester, not latest-completed actual | live completed-semester SGPA (CSE Sem6, BBA Sem4) | Sem6 (CSE) / Sem4 (BBA) actual SGPA | DERIVE_FROM_AUTHORITATIVE_DATA | HIGH | CSE: STU000032/041 verify against Sem6; see Sec 4 | Isolated from M1/M2/M3 (forbidden) but served to UIs/analytics |
| ISS-002 | CRITICAL | ETL derive.py | student_semester_summary | 50 rows (CSE) | CSE-1..50 | 7 | semester_total_marks/percentage/sgpa/grade/result/backlog_count/credits_earned | 0.0 / 0.0 / 0.0 / B / PASS / 0 / =reg(19) | live: sgpa 0.0, total 0.0, pct 0.0, PASS 50, B 50, backlog 0, cred=reg | PLACEHOLDER/CONTRADICTORY: outcome fields populated while 349/350 end-sem NULL | subject-level marks (end-sem NULL) | keep attendance/credits_registered; NULL all academic outcomes | SET_TO_NULL | HIGH | — | M2/M3 features (Sem7 deploy) still wrong until rebuilt |
| ISS-003 | CRITICAL | ETL derive.py / seed | student_semester_summary | 30 rows (BBA) | BBA-1..30 | 5 | total/percentage/sgpa/grade/result/backlog/credits_earned | fabricated (sgpa 1.59–10.0, PASS 26/ATKT 4, grade incl F=4, backlog>0=4, cred≠reg) | live BBA Sem5: 0 end-sem marks yet full summary | PLACEHOLDER/FABRICATED: no supporting subject marks | subject-level marks (end-sem NULL) | NULL academic outcomes; keep reg/attendance if present | SET_TO_NULL | HIGH | — | M2/M3 features/deploy |
| ISS-004 | CRITICAL | seed 06 / ml CSV | ml/data/raw/student_semester_summary_rows.csv | 50 rows (CSE Sem7) | CSE-1..50 | 7 | semester_sgpa & co | fabricated migration-seed (7.84 etc.) | CSV Sem7 holds seed values; live=zeroed; no agreement | CSV ≠ live; stale fabricated snapshot fed to M2/M3 | live corrected DB | re-derive CSV from corrected DB (or NULL) | DERIVE_FROM_AUTHORITATIVE_DATA / REMOVE | HIGH | — | M2/M3 T+1 targets + deploy features |
| ISS-005 | HIGH | seed 06 | ml/data/raw/student_semester_summary_rows.csv | 50 CSE Sem7 + 30 BBA Sem5 | CSE-1..50, BBA-1..30 | 7 / 5 | T+1 targets for M2/M3 | fabricated Sem7/Sem5 values | 80 last-training-rows per student CSE-Sem6/BBA-Sem4 carry these as next-sem | INVALID T+1 supervision | actual completed next-sem outcomes (none) | dataset rows have NO valid target → remove from training | REMOVE_FROM_TRAINING | HIGH | — | M2/M3 training (80/420 = 19%) |
| ISS-006 | HIGH | seed 06 + ml CSV | M3 labels | 6 placeholder positives | STU000032,041,052,060,064,075 | last (6/4) → (7/5) | is_at_risk_next_sem=1 | label derived from fabricated ATKT | last-row target ATKT/backlog from fabricated sem | INVALID positive label (fabricated source) + TLS-bound | actual completed outcome (none) | remove these 6 last-row positives from training | REMOVE_FROM_TRAINING | HIGH | — | M3 |
| ISS-007 | MEDIUM | seed / ml CSV | ml/data/raw/student_subject_performance_rows.csv | 3 rows | STU000002,003,004 | 7 | end_sem_marks | CSV: SUB0050 end=40/40/45 | live DB end-sem non-null=1 (STU000002/SUB0053=25); CSV rows not in live | stale/fabricated/wrong subject+value | live performance record | remove from M1 training (not authoritative) | REMOVE_FROM_TRAINING | HIGH | STU000002 subject mismatch confirmed see Sec 3 | M1 (3 rows) |
| ISS-008 | MEDIUM | seed/record | student_semester_summary (live) | STU000002 Sem4/5/6 | STU000002 | 4,5,6 | semester_sgpa | 9.23/9.62/9.99 | recompute=10.0 (matches CSV) | drift in stored sgpa | subject grade_point×credits recompute | 10.0 / 10.0 / 10.0 | DERIVE_FROM_AUTHORITATIVE_DATA | HIGH | — | summary, overall_cgpa |
| ISS-009 | MEDIUM | seed/record | students.students total_backlogs | 7 students | 032,041,052,060,064,075,017 | — | total_backlogs | 24/25/17/16/13/16/1 | reconstructed subject-fails=21/23/12/11/10/13/0 | inflated; not derivable from failures | subject fail counts (completed sems) | 21/23/12/11/10/13/0 | DERIVE_FROM_AUTHORITATIVE_DATA | HIGH | — | UIs/analytics; NOT in M1/M2/M3 |
| ISS-010 | LOW | pipeline | daily_attendance_07 | N/A | - | — | attendance granularity | BBA has no daily-lecture rows | daily_attendance_07 = CSE Sem7 only | structural BBA gap (not a value error) | — | no action; document | NO_ACTION / MANUAL_REVIEW | MEDIUM | confirm intended | attendance analytics for BBA sem>4 |
| ISS-011 | MEDIUM | read-only audit | (speculation check) | — | — | — | — | — | nothing here | confirmed | none | none | NO_ACTION | HIGH | none | —

> Note: ISS-002 vs ISS-003 differ in presentation (CSE zeroed vs BBA fabricated) but BOTH violate the invariant; both corrected to NULL. ISS-004 (CSV snapshot) becomes a snapshot rebuild after DB fix; ISS-005/006 are dataset-level (REMOVE_FROM_TRAINING) not DB-record corruption.

---

## SECTION 2 — CSE SEMESTER 7 CORRECTION SPECIFICATION

**Scope:** 50 CSE students, all at Sem-7 (incomplete). For each student, `student_semester_summary` (50 rows), `student_subject_performance` (350 subject rows, 349 end-sem NULL), `attendance` (aggregate present), `students.latest_sgpa` (seeded Sem7).

**Field-by-field matrix (applies identically to all 50 CSE students; STU000002 is the single exception for subjects):**

| student_id | semester | field | current_value | expected_value | reason | source_of_truth | confidence |
|---|---|---|---|---|---|---|---|
| CSE STU000001…000050 | 7 | semester_total_marks | 0.0 | **NULL** | 349/350 end-sem absent; cannot derive | subject marks | HIGH |
| CSE STU000001…000050 | 7 | semester_percentage | 0.0 | **NULL** | not derivable without end-sem | subject marks | HIGH |
| CSE STU000001…000050 | 7 | semester_sgpa | 0.0 | **NULL** (do NOT use M2 predicted 6.25 etc.) | incomplete | subject marks | HIGH |
| CSE STU000001…000050 | 7 | semester_grade | B | **NULL** | incomplete | subject marks | HIGH |
| CSE STU000001…000050 | 7 | semester_result | PASS | **NULL** | incomplete | subject marks | HIGH |
| CSE STU000001…000050 | 7 | backlog_count | 0 | **NULL / not yet determined** | no completed end-sem outcome | subject marks | HIGH |
| CSE STU000001…000050 | 7 | credits_earned | 19 (=reg) | **NULL / not yet determined** except STU000002 (see below) | no completed outcome | subject marks | HIGH |
| CSE STU000001…000050 | 7 | semester_attendance_percentage | (present) | **KEEP / PRESERVE** | attendance real | attendance | HIGH |
| CSE STU000001…000050 | 7 | credits_registered / subjects_registered | 19 | **KEEP / PRESERVE** | enrollment real | enrollment | HIGH |

**Exception — STU000002 (the single genuinely completed Sem-7 subject):**
- Live: `STU000002 / SUB0053` = internal 18 + mid 49 + end 25 = total 92, grade B+, result Pass → this is a **valid completed subject**.
- This subject's derived fields (total_marks=92, grade=B+, result=Pass) are **DERIVED_FROM_AUTHORITATIVE_DATA** and must be **PRESERVED** (they are consistent).
- However because only 1 of ~7 Sem-7 subjects is complete, the **Sem-7 SUMMARY for STU000002 still cannot be computed** (grade_point×credits across a partial semester is not an authoritative SGPA). → **summary stay NULL** while the 1 valid subject row is preserved. This is NOT a contradiction: subject-level valid, semester-level incomplete.
- **Confidence: HIGH** for keeping the subject row; **HIGH** that summary stays NULL.

Do NOT zero STU000002's summary; leave it NULL. Do NOT fabricate the other 6 subjects.

---

## SECTION 3 — STALE / FABRICATED SEM-7 END-SEM RECORDS

These three rows exist **only in `ml/data/raw/student_subject_performance_rows.csv`**; the live authoritative DB has a different truth.

| student_id | table/file | subject | current CSV end_sem | live DB truth | exists in authoritative source? | classification | proposed correction | downstream ML rows |
|---|---|---|---|---|---|---|---|---|
| STU000002 | ml/data/raw/...performance_rows.csv | SUB0050 | 40.0 | live Sem-7 genuine subject is **SUB0053** (end 25.0); SUB0050 not the live completed one | **NO** (SUB0050 is absent in live as completed; live completed subject is SUB0053) | **STALE/INVALID** (wrong subject + wrong value) | REMOVE_FROM_TRAINING; do not substitute | M1 training (1 row) |
| STU000003 | ml/data/raw/...performance_rows.csv | SUB0050 | 40.0 | live: STU000003 Sem-7 end-sem = NULL (0 completed subjects) | **NO** | **FABRICATED** (no live end-sem) | REMOVE_FROM_TRAINING | M1 training (1 row) |
| STU000004 | ml/data/raw/...performance_rows.csv | SUB0050 | 45.0 | live: STU000004 Sem-7 end-sem = NULL | **NO** | **FABRICATED** | REMOVE_FROM_TRAINING | M1 training (1 row) |

- **STU000002 subject/value mismatch confirmed independently:** the forensic audit flagged it; live DB shows STU000002/SUB0053=25, not SUB0050=40. These are distinct records → the CSV row is stale/wrong, not legitimately historical.
- **STU000003/STU000004 end_sem are not in the live DB at all** → fabricated for Sem-7. Do not delete subject rows (internal/mid/attendance may still be genuine); only their end_sem should be treated as non-authoritative, and the rows excluded from M1 training.

---

## SECTION 4 — students.latest_sgpa

**Verified:** `students.latest_sgpa` = fabricated Sem-7 CSR (CSE) / Sem-5 (BBA) for **ALL 80 students** (50/50 and 30/30 match). Proposed value = latest **completed** actual SGPA (CSE Sem6, BBA Sem4). Recomputed from live DB. All HIGH confidence (directly derivable). Summary table of the notable mismatches (full recompute available; all 80 divergent from current):

| student_id | current_latest_sgpa | latest_completed_actual_sem | actual_latest_sgpa | diff | source | classification | proposed_value | reason | confidence |
|---|---|---|---|---|---|---|---|---|---|
| STU000001 | 7.84 | 6 | 7.77 | +0.07 | live summary/SGPA recompute | SEEDED (Sem7) | 7.77 | latest completed actual | HIGH |
| STU000002 | 10.00 | 6 | 9.99 | +0.01 | live summary | SEEDED (Sem7) | 9.99 | latest completed actual (Sem6) | HIGH |
| STU000032 | 2.89 | 6 | 3.64 | -0.75 | live summary | SEEDED (fabricated Sem7 2.89) | 3.64 | latest completed actual (Sem6, genuine ATKT student) | HIGH |
| STU000041 | 3.42 | 6 | 4.32 | -0.90 | live summary | SEEDED (fabricated Sem7 3.42) | 4.32 | latest completed actual | HIGH |
| STU000017 | 5.84 | 6 | 6.00 | -0.16 | live summary | SEEDED | 6.00 | latest completed actual | HIGH |
| STU000008 | 5.84 | 6 | 6.00 | -0.16 | live summary | SEEDED | 6.00 | latest completed actual | HIGH |
| STU000052 (BBA) | 1.59 | 4 | 2.50 | -0.91 | live summary | SEEDED (fabricated Sem5) | 2.50 | latest completed actual | HIGH |
| STU000060 (BBA) | 1.59 | 4 | 4.00 | -2.41 | live summary | SEEDED | 4.00 | latest completed actual | HIGH |
| STU000064 (BBA) | 2.73 | 4 | 4.60 | -1.87 | live summary | SEEDED | 4.60 | latest completed actual | HIGH |
| STU000075 (BBA) | 2.73 | 4 | 4.00 | -1.27 | live summary | SEEDED | 4.00 | latest completed actual | HIGH |
| ... (all other 70) | varies | 6(CSE)/4(BBA) | computed | small ±0.3 | live summary | SEEDED | Sem6/Sem4 actual | latest completed actual | HIGH |

**Rule:** `latest_sgpa` semantically = **latest completed-semester SGPA** → set to sem6 (CSE) / sem4 (BBA) actual SGPA for all 80. Any student whose completed-sgpa cannot be reconstructed → NULL. Do NOT substitute the fabricated Sem-7/Sem-5 value, and do NOT use predicted SGPA.

---

## SECTION 5 — students.total_backlogs

Verified recompute from subject `result_status='Fail'` over completed sems (CSE Sem1-6, BBA Sem1-4). `summary.backlog_count` (completed) == subject-fails for all; store `students.total_backlogs` inflated.

| student_id | current total_backlogs | sem backlog counts (from completed summary) | independently reconstructed total (subject fails) | source records | discrepancy | proposed value | state | confidence |
|---|---|---|---|---|---|---|---|---|
| STU000032 | 24 | Σ=21 | 21 | perf fails + sem summary | Δ=3 | 21 | VERIFIED ACTUAL VALUE | HIGH |
| STU000041 | 25 | Σ=23 | 23 | perf fails + sem summary | Δ=2 | 23 | VERIFIED ACTUAL VALUE | HIGH |
| STU000052 | 17 | Σ=12 | 12 | perf fails + sem summary | Δ=5 | 12 | VERIFIED ACTUAL VALUE | HIGH |
| STU000060 | 16 | Σ=11 | 11 | perf fails + sem summary | Δ=5 | 11 | VERIFIED ACTUAL VALUE | HIGH |
| STU000064 | 13 | Σ=10 | 10 | perf fails + sem summary | Δ=3 | 10 | VERIFIED ACTUAL VALUE | HIGH |
| STU000075 | 16 | Σ=13 | 13 | perf fails + sem summary | Δ=3 | 13 | VERIFIED ACTUAL VALUE | HIGH |
| STU000017 | 1 | Σ=0 | 0 | perf fails (0) | Δ=1 | 0 | VERIFIED ACTUAL VALUE | HIGH |
| all other 73 | (leave) | Σ = subject fails | subject fails | perf fails | 0 | unchanged | PRESERVE | HIGH |

Rule: `total_backlogs` = Σ backward-count across completed sems = Σ subject fails. Do NOT add Sem-7/Sem-5 fabricated counts (still incomplete). Never fabricate.

---

## SECTION 6 — BBA SEEDED / SEM-5 DATA

**Structural (ACTUAL/DERIVED, preserve):** 30 BBA students; enrollment (210/sem), attendance aggregate Sem1-5 (210/sem), internal+mid marks Sem1-5 (210/sem each), end-sem marks **Sem1-4** (210/sem), summaries **Sem1-4** (derived, valid).

**Sem-5 (PLACEHOLDER/FABRICATED, → NULL for academic outcomes):** 0 end-sem marks but live summary fully populated (PASS 26/ATKT 4, SGPA 1.59-10.0, grade incl. F=4, backlog>0=4, cred≠reg). For all 30 BBA students: `semester_total_marks/percentage/sgpa/grade/result/backlog/credits_earned` → **NULL**; keep `subjects_registered/credits_registered/attendance` where real. Do NOT invent BBA attendance/marks/SGPA/result/backlog. Confidence HIGH (0 supporting subject marks).

**Notable failing BBA students (Sem1-4 completed, actual):** STU000052 (sem4 SGPA 2.50, 12 fails), STU000060 (4.00, 11 fails), STU000064 (4.60, 10 fails), STU000075 (4.00, 13 fails) — their Sem1-4 records are genuine; only their Sem-5 summary + latest_sgpa/total_backlogs are affected (see Sec 4/5).

---

## SECTION 7 — M1 CORRECTION SPECIFICATION

M1 trains on end_sem NOT NULL = **3,293 rows** (CSE 2,453 + BBA 840). Affected rows (7): 3 stale/fabricated Sem-7; plus 0 leakage from latest_sgpa/total_backlogs (forbidden). STU000002 Sem4/5/6 summary drift (ISS-008) affects M1 only if ablation prior aggregates used (ablation OFF by default) → NOTE for rebuild.

| dataset row identifier | student_id | semester | subject | current target (end_sem) | target source | why invalid | proposed action |
|---|---|---|---|---|---|---|---|
| csv perf row idx 105 | STU000002 | 7 | SUB0050 | 40.0 | CSV stale/fabricated | not in live; live uses SUB0053=25 | REMOVE_FROM_TRAINING |
| csv perf row idx 161 | STU000003 | 7 | SUB0050 | 40.0 | CSV fabricated | no live end-sem | REMOVE_FROM_TRAINING |
| csv perf row idx 217 | STU000004 | 7 | SUB0050 | 45.0 | CSV fabricated | no live end-sem | REMOVE_FROM_TRAINING |
| (all other 3,290) | — | 1-6 (CSE/BBA) | — | genuine end_sem | live-derived | valid | KEEP |

- After removal: 3,290 training rows (CSE 2,450 + BBA 840). M1 ready to **REBUILD_FROM_AUTHORITATIVE_SOURCE** (re-derive CSV from corrected DB), then retrain.
- No other M1 leakage found. Ablation-mode prior aggregates use Sem1-6 summary only (genuine). Verify STU000002 Sem4/5/6 sgpa correction before using ablation.

---

## SECTION 8 — M2 CORRECTION SPECIFICATION

M2 training = 420 rows (last row/student = CSE Sem6 [50] + BBA Sem4 [30] = 80 rows). These 80 have T+1 from **fabricated Sem-7/Sem-5** → invalid supervision.

| student_id | source_sem | target_sem | target_field | current_target | target_source | why invalid | authoritative target available? | proposed action |
|---|---|---|---|---|---|---|---|---|
| CSE all 50 | 6 | 7 | sem7 pct/sgpa | CSV fabricated (e.g. STU000001 7.84/72.86) | ml/data/raw synthesized Sem7 | Sem7 incomplete; no actual | NO (Sem7 not completed) | REMOVE_FROM_TRAINING |
| BBA all 30 | 4 | 5 | sem5 pct/sgpa | fabricated (e.g. STU000052 1.59) | ml/data/raw synthesized Sem5 | Sem5 incomplete; no actual | NO (Sem5 not completed) | REMOVE_FROM_TRAINING |

- **CRITICAL:** Sem6→**predicted** Sem7 SGPA must NOT be used as the Sem6→actual Sem7 target. Because actual Sem7 does not exist, these 80 rows are **not valid supervised training examples** → remove. Result: **M2 training = 340 rows** (CSE 250 = sems1-5→2-6; BBA 120 = sems1-4(?) → recompute: CSE training without last row = 300-50=250; BBA without last =120-30=90; total 340).
  - Recompute: CSE complete→target sems: sources sem1..5 (5×50=250). BBA sources sem1..3 (3×30=90). Total 340. **Manual count to confirm at rebuild.**

---

## SECTION 9 — M3 CORRECTION SPECIFICATION

M3 positives = 28/420 (6.7%), all from 6 chronically-failing students. **6 last-row positives** (CSE Sem6→Sem7: STU000032, STU000041; BBA Sem4→Sem5: STU000052, STU000060, STU000064, STU000075) are **label-only placeholders (fabricated live-semester ATKT)** → REMOVE_FROM_TRAINING.

The other **22 positives** (STU000032/041 CSE Sem1-5→2-6; STU000052/060/064/075 BBA Sem1-3→2-4) are derived from **actual completed ATKT** → **KEEP (VALID)**.

| label group | students | source sems | target sems | #labels | status | action |
|---|---|---|---|---|---|---|
| Placeholder positives (live-semester) | STU000032,041 (CSE sem6), STU000052,060,064,075 (BBA sem4) | last | fabricated 7/5 | 6 | INVALID | REMOVE_FROM_TRAINING |
| Valid positives (actual ATKT) | same 6 students | earlier sems | actual completed | 22 | VALID | KEEP |
| Negatives (actual PASS/0-backlog) | all 80 | various | actual completed | 392 (of 420 pool) | VALID | KEEP (minus invalid rows) |

- After removing 6 invalid positives + 80 invalid T+1 **training rows** (the last rows are entirely removed since they have no valid target — this removes both positives and negatives at the boundary): recompute training = 340 rows; valid positives within = those with actual completed next-semester ATKT. **Do NOT relabel to fix balance; do NOT create artificial positives.**

---

## SECTION 10 — PREDICTION TABLES

Verified read-only. **M2 write-back is CLEAN**:
- `ml_prediction_repo.py` = **append-only** `INSERT INTO ml_predictions` (lines 118/159) only.
- `prediction_contract_service.py` = **read-only**, "NEVER writes predictions back".
- `prediction_generation_service` → persists only to `ml_predictions` (JSONB `prediction_value`).
- No application UPDATE to `student_semester_summary` or `students.latest_sgpa` carries prediction values (the only `students`/`summary` UPDATEs are the ETL derivation path).

Classification:
- `ml_predictions.prediction_value` = **PREDICTION**.
- `ml_predictions.generated_at` = **PREDICTION metadata** (timestamps, PRESERVE).
- `students.latest_sgpa` = SEEDED/ACTUAL (see Sec 4) — must be re-derived, but predictions must NOT be written here.
- `risk_predictions` (80 rows) = legacy seeded statuses, treated as PREDICTION/label, NOT ground truth.
- `prediction_feedback` = **FEEDBACK** — preserve unless independently proven invalid.
**Do NOT modify prediction records.** Keep separation.

---

## SECTION 11 — CSV CORRECTION SPECIFICATION

Actual file is **`students_rows.csv`** (under `ml/data/raw/`); there is NO `Student_row.csv`. The CSVs affected by the discovered problems:

| file | row / grain | student_id / sem | field | current_value | classification | proposed_value | reason | source |
|---|---|---|---|---|---|---|---|---|
| students_rows.csv | 1..80 | all | latest_sgpa | seeded Sem7/Sem5 | SEEDED | Sem6/Sem4 actual | latest completed actual | DB (after correction) |
| students_rows.csv | 1..80 | all | total_backlogs | inflated (7 students) | SEEDED | subject-fail Σ | reconstructed | DB |
| student_semester_summary_rows.csv | CSE Sem7 (50) | CSE | sem7 sgpa/pct/result/backlog | fabricated seed | SEEDED | NULL / rebuilt | incomplete | DB (after correction) |
| student_semester_summary_rows.csv | BBA Sem5 (30) | BBA | sem5 fields | fabricated | SEEDED | NULL / rebuilt | incomplete | DB |
| student_subject_performance_rows.csv | 3 rows | STU000002/003/004 Sem7 | end_sem_marks | 40/40/45 (fabricated) | INVALID | not authoritative; keep subject rows but end_sem treated absent | live DB mismatch | DB |

CSV does not contain prediction values in these academic files (predictions live in `ml_predictions` / export `ml_predictions.csv`). **Do not modify the CSV; rebuild from corrected DB in correction Phase 4/5.**

---

## SECTION 12 — SEED MIGRATION ROOT CAUSE

- **Migration:** `migrations/06_student_semester_summary_data.sql` — populates `student_semester_summary` (500 INSERTs) including **fabricated Sem-7 (CSE)** and **Sem-5 (BBA)** rows with full SGPA/result/backlog.
- **Migration:** `migrations/03_students_data.sql` — seeds `students.latest_sgpa`, `overall_cgpa`, `overall_percentage`, `total_backlogs`, `total_credits_earned` for all 80, using the same fabricated live-semester SGPA (verified 50/50 CSE and 30/30 BBA match Sem-7/Sem-5 CSV SGPA).
- **Migration:** `migrations/09_risk_predictions_data.sql` — 80 legacy seeded risk statuses.
- **Intended purpose:** synthetic demo/seed cohort (all `admission_year 2023`, fabricated academic_year 2026-27). Values are **clearly synthetic/seeded** — NOT actual academic outcomes.
- **Propagation:** seed → CSV snapshots (`ml/data/raw`) → M2/M3 T+1 targets + deploy features → M1 (3 end-sem rows). Live DB kept a *different* (zeroed) placeholder in summary but the **seeded latest_sgpa remained in students**. Root cause: the ETL/trigger only NULLs the incomplete subject level, and summaries + latest_sgpa were populated by seed and not recomputed to NULL. **Documenting only — do NOT modify the migration.**

---

## SECTION 13 — DOWNSTREAM IMPACT MAP (verified propagation)

```
seed 06/03 (fabricated Sem7/Sem5)
   ├──> student_semester_summary (live: zeroed   [CSE] / fabricated [BBA])      → ISS-002/003
   │         └──> students.latest_sgpa (=Sem7/Sem5)                             → ISS-001  (verified 80/80)
   │         └──> students.total_backlogs (inflated)                            → ISS-009  (verified 7)
   ├──> ml/data/raw/student_semester_summary_rows.csv (fabricated)               → ISS-004
   │         └──> M2 dataset (T+1 targets at CSE-Sem6/BBA-Sem4 last rows)        → ISS-005 (80 rows)
   │         └──> M3 dataset (6 placeholder positives, 28 total)                 → ISS-006
   ├──> ml/data/raw/student_subject_performance_rows.csv (3 Sem7 end_sem rows)  → ISS-007 → M1
   └──> students_rows.csv (latest_sgpa/total_backlogs)
            └──> M2/M3 features (NOT used: forbidden)  → no model propagation
```
- `latest_sgpa`/`total_backlogs` are in M1/M2/M3 **forbidden columns** → do **NOT** affect model features (verified in m1/config.py, v1_config.py). Their impact is via UI/analytics and summary, not model inputs.
- M1 impact limited to the 3 subject rows; M2/M3 impact via summary CSV.

---

## SECTION 14 — CORRECTION ORDER (planned, NOT executed)

PHASE 1 – Correct source academic records (end-sem marks) for Sem-7/Sem-5, or confirm incompleteness.
PHASE 2 – Rebuild/set derived `student_semester_summary` for CSE-Sem7 & BBA-Sem5 to NULL (academic outcomes), fix STU000002 Sem4/5/6 sgpa.
PHASE 3 – Re-derive `students.latest_sgpa` and `students.total_backlogs` from latest-completed actuals.
PHASE 4 – Rebuild `ml/data/raw/*.csv` snapshots (`students_rows.csv`, summaries, performance) from corrected DB.
PHASE 5 – Rebuild M1 dataset (drop 3 stale Sem7 rows) → 3,290.
PHASE 6 – Rebuild M2 dataset (drop 80 boundary rows) → 340.
PHASE 7 – Rebuild M3 dataset (drop 80 boundary rows; 6 placeholder positives excluded) → 340 rows.
PHASE 8 – Retrain M1/M2/M3 on corrected datasets (new artifacts, new SHA-256).
PHASE 9 – Validate (temporal holdout, label sanity).
PHASE 10 – Only then update deployment artifacts/API.

Why this order: fixing source records FIRST prevents fabricated values from propagating into summaries, student fields, CSVs, and finally into model training labels. Rebuilding CSVs only after DB is correct guarantees M2/M3 T+1 targets come from real completed outcomes.

---

## SECTION 15 — DO NOT TOUCH LIST

| Item | Why preserve |
|---|---|
| Valid actual subject marks (internal/mid/end of COMPLETED sems) | authoritative base of all derivations |
| Valid actual attendance records | authoritative; real |
| Valid completed-semester summaries (CSE Sem1-6, BBA Sem1-4) | derived from valid marks; correct |
| STU000002/SUB0053 Sem7 subject row | a genuinely completed subject (total 92, B+, Pass) |
| Valid ml_predictions rows + timestamps | forward-looking predictions; separation is correct |
| prediction_feedback | feedback record; preserve unless proven invalid |
| Model artifacts + SHA-256 (3404D29E, 6CAC9A88, 99D845FE) | current models are the deploy state until retrain |
| Correct DB trigger `trg_calculate_performance` | correctly NULLs incomplete subject level |
| BBA Sem-5 internal/mid/attendance (present) | real where present; only outcomes are NULL |

---

## SECTION 16 — REQUIRED VERIFICATION QUERIES (READ-ONLY, for AFTER correction)

Do not run modifications — these SELECTs verify a FUTURE corrected state.

```sql
-- V1: no incomplete CSE Sem7 row has non-NULL actual SGPA/percentage/grade/result/backlog
SELECT count(*) FROM student_semester_summary s
JOIN students st ON st.student_id=s.student_id
WHERE st.department_name='CSE' AND s.semester_no=7
  AND (s.semester_sgpa IS NOT NULL OR s.semester_percentage IS NOT NULL
       OR s.semester_grade IS NOT NULL OR s.semester_result IS NOT NULL
       OR s.backlog_count IS NOT NULL);

-- V2: BBA Sem5 academic outcomes NULL
SELECT count(*) FROM student_semester_summary s
JOIN students st ON st.student_id=s.student_id
WHERE st.department_name='BBA' AND s.semester_no=5
  AND (s.semester_sgpa IS NOT NULL OR s.semester_result IS NOT NULL OR s.backlog_count IS NOT NULL);

-- V3: all completed Sem1-6 (CSE)/Sem1-4 (BBA) summaries still populated (not lost)
SELECT st.department_name, s.semester_no, count(*) FILTER (WHERE s.semester_sgpa IS NOT NULL) AS ok
FROM student_semester_summary s JOIN students st ON st.student_id=s.student_id
GROUP BY 1,2 ORDER BY 1,2;

-- V4: no fabricated Sem7 end_sem remains feeding M1 (approved STU000002/SUB0053 only)
SELECT count(*) FROM student_subject_performance p
JOIN students st ON st.student_id=p.student_id
WHERE st.department_name='CSE' AND p.semester_no=7 AND p.end_sem_marks IS NOT NULL;

-- V5: students.latest_sgpa == latest completed actual sgpa (CSE Sem6, BBA Sem4)
WITH lat AS (
  SELECT DISTINCT ON (ss.student_id) ss.student_id, ss.semester_sgpa
  FROM student_semester_summary ss JOIN students st ON st.student_id=ss.student_id
  WHERE (NOT (st.department_name='CSE' AND ss.semester_no=7))
    AND (NOT (st.department_name='BBA' AND ss.semester_no=5))
  ORDER BY ss.student_id, ss.semester_no DESC)
SELECT count(*) FROM students st LEFT JOIN lat ON lat.student_id=st.student_id
WHERE abs(st.latest_sgpa - lat.semester_sgpa) > 0.005;

-- V6: total_backlogs vs reconstructed subject failures
SELECT st.student_id, st.total_backlogs,
       (SELECT count(*) FROM student_subject_performance p
        WHERE p.student_id=st.student_id AND p.result_status='Fail'
          AND NOT (st.department_name='CSE' AND p.semester_no=7)
          AND NOT (st.department_name='BBA' AND p.semester_no=5)) AS rec_backlog
FROM students st WHERE st.total_backlogs <> 0;

-- V7: M2 training contains only valid actual T+1 (count boundary rows that must be gone)
--   (dataset-level check after rebuild; assert last training row is NOT the live semester):
--   total M2 training rows should equal 340 (CSE 250 + BBA 90), last source sem = 5 (CSE) / 3 (BBA).

-- V8: M3 labels derive only from actual outcomes (no placeholder positives):
--   count positives whose source-semester is the boundary (CSE sem6 / BBA sem4) == 0 after rebuild.

-- V9: no M2 predicted sgpa present in summary/latest_sgpa:
SELECT count(*) FROM ml_predictions WHERE prediction_value->>'semester' IS NOT NULL;  -- sanity, untouched
SELECT count(*) FROM student_semester_summary s
JOIN students st ON st.student_id=s.student_id
WHERE st.department_name='CSE' AND s.semester_no=7 AND s.semester_sgpa IN (6.25, 57.51);  -- M2-pred style absent
```

---

## SECTION 17 — CONFIDENCE / MANUAL REVIEW

All core corrections (ISS-001..009) are **HIGH** confidence (directly derived from authoritative live subject/summary records, verified above). Every HIGH item may be applied automatically in the correction phase. Items requiring MANUAL_REVIEW:

- **ISS-010** (BBA daily-attendance structural gap) — MEDIUM; confirm intended scope.
- **STU000002** Sem-7 summary handling interplay with its one valid subject (SUB0053) — HIGH for subject preservation, but the semester-level decision "summary NULL despite 1 valid subject" should be *confirmed* by the data owner → **MANUAL_REVIEW (HIGH evidence, one-time sign-off).**
- Any LOW-confidence case: none found that matter to ML; flag semantic intent of `latest_sgpa` (completed vs "pending live") — confirm with owner → MANUAL_REVIEW as a *semantics decision*, not a data-integrity one.

No automatic modification for anything that cannot be derived; all non-derivable → NULL/MANUAL_REVIEW.

---

## SECTION 18 — FINAL RECORD COUNTS (reconciled)

| Category | Count |
|---|---|
| Total affected DB summary rows (CSE Sem7 50 + BBA Sem5 30) | 80 |
| Affected subject-performance rows (CSE Sem7 350 end-sem involved; only 1 genuine) | 350 (1 genuine, 349 treated incomplete) |
| Affected students.latest_sgpa | 80 |
| Affected students.total_backlogs | 7 |
| STU000002 Sem4/5/6 summary sgpa drift | 3 |
| **Total affected DB records** | **80 (summary) + 80 (latest_sgpa) + 7 (backlogs) + 3 (sgpa drift) = 170** |
| Affected CSV rows (students_rows latest_sgpa 80 + backlogs 7 + summary CSE-Sem7 50 + BBA-Sem5 30 + perf 3) | 170 (80+7+50+30+3, some overlap by field) |
| Affected CSE students | 50 |
| Affected BBA students | 30 |
| Affected DB summary rows for live semester | 80 (CSE Sem7 50 + BBA Sem5 30) |
| Affected M1 rows | 3 (training) |
| Affected M2 rows (training) | 80 |
| Affected M3 rows (training) | 80 (rows) / 6 placeholder positives (labels) |
| Automatically correctable (HIGH, derived) | summary 80 + latest_sgpa 80 + backlogs 7 + sgpa drift 3 = 170 |
| Should become NULL | CSE Sem7 7 outcome-fields ×50; BBA Sem5 7 fields ×30; (structure-level) |
| Requiring manual review | ISS-010 (structural), STU000002 sem7-summary sign-off, latest_sgpa semantics |
| Requiring no action | all valid completed records (CSE Sem1-6, BBA Sem1-4), all valid predictions, valid subject rows |

Reconciliation: affected DB records 170 = summary 80 + students 80 (latest_sgpa, same rows also carry backlogs for 7 of them) + summary-drift 3 (STU000002; counted within the 50 CSE students). The 3 M1 / 80 M2 / 80 M3 rows are dataset-row impacts, distinct from DB records.

---

## SECTION 19 — FINAL CORRECTION SPECIFICATION

**CRITICAL — MUST CORRECT BEFORE ML RETRAINING**
1. Set CSE Sem-7 (50) and BBA Sem-5 (30) `student_semester_summary` academic-outcome fields (total/percentage/sgpa/grade/result/backlog/credits_earned) to **NULL**; keep attendance/credits_registered. (ISS-002/003)
2. Re-derive `students.latest_sgpa` to latest **completed** actual SGPA (CSE Sem6, BBA Sem4) for all 80 (currently fabricated Sem7/Sem5). (ISS-001)
3. Remove the 80 boundary M2/M3 training rows (CSE Sem6→Sem7, BBA Sem4→Sem5) — no valid actual T+1; remove the 6 M3 placeholder positives and the 3 M1 fabricated Sem-7 end-sem rows. Rebuild CSV snapshots from corrected DB. (ISS-004..007)

**HIGH — SHOULD CORRECT**
1. Fix `students.total_backlogs` to reconstructed subject-fail Σ for the 7 students (032:21, 041:23, 052:12, 060:11, 064:10, 075:13, 017:0). (ISS-009)
2. Fix STU000002 Sem4/5/6 `semester_sgpa` to 10.0 (recomputed). (ISS-008)
3. Rebuild M1 (→3,290), M2 (→340), M3 (→340) datasets from corrected DB; retrain with new artifacts + new SHA-256.

**MEDIUM — CAN FOLLOW AFTER CORE DATA FIX**
1. Reconcile `overall_cgpa`/`overall_percentage`/`overall_attendance_percentage` against corrected completed semesters.
2. Decide/recommend semantics of `latest_sgpa` (document "latest completed" contract).
3. Address BBA daily-attendance structural gap (ISS-010) if in scope.

**PRESERVE — DO NOT TOUCH**
1. All valid completed-subject marks, attendance, and Sem1-6 (CSE)/Sem1-4 (BBA) summaries.
2. STU000002/SUB0053 genuine Sem-7 subject row; the `trg_calculate_performance` trigger.
3. All `ml_predictions` (values + timestamps), `risk_predictions`, `prediction_feedback`; model artifacts + SHA-256 until retrain.

**MANUAL REVIEW REQUIRED**
1. STU000002 Sem-7 rule: 1 valid subject (SUB0053) but summary kept NULL — data-owner sign-off.
2. `latest_sgpa` semantics (completed-actual vs pending-live) — confirm contract before re-deriving.
3. BBA Sem5 internal/mid/attendance retention vs any intended additional marks entry.

**M1:** READY AFTER: Phase 4/5 rebuild drops the 3 stale Sem-7 end-sem rows → 3,290-row training (CSE 2,450 + BBA 840), retrain, validate. PARTIALLY_READY → READY.

**M2:** READY AFTER: Phase 6 rebuild removes the 80 boundary rows (no valid actual Sem-7/Sem-5 targets) → 340-row training with valid actual T+1 only; retrain. NOT_READY → READY.

**M3:** READY AFTER: Phase 7 rebuild removes 80 boundary rows + 6 placeholder positives → 340-row training, labels only from actual completed ATKT/backlog; verify positive-class sufficiency (gate) before retrain; otherwise BLOCKED. NOT_READY → READY (gate-dependent).

---

## FINAL SAFETY VERIFICATION

1. **No database write occurred** — all queries were read-only (`default_transaction_read_only=on`); only SELECTs run.
2. **No CSV modified** — all CSV analysis read via pandas; no writes to `ml/data/raw/*`.
3. **No ML model retrained** — artifacts unmodified; SHA-256 re-verified identical (m1 3404D29E…, m2 6CAC9A88…, m3 99D845FE…).
4. **No prediction record modified** — `ml_prediction_repo`/services not executed; no UPDATE/INSERT run.
5. **No model artifact modified** — hash fingerprints unchanged.

**"NO DATABASE, CSV, ML DATASET, MODEL, PREDICTION RECORD, OR PROJECT CODE WAS MODIFIED BY THIS CORRECTION-SPECIFICATION AUDIT."**

*Footer: STRICT READ-ONLY — specification ONLY, not the correction. No DB writes/DDL/migrations, no CSV/model/ETL/API/UI changes, no data fabrication, no NULL filling, no silent corrections, no use of ML predictions as actual academic outcomes.*
