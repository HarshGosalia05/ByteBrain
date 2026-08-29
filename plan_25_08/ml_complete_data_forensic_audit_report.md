# ByteBrain — ML Complete Data Forensic Audit Report (19-Section)

**Report ID:** `ML-COMPLETE-DATA-FORENSIC-AUDIT-2026-08-29`
**Auditor discipline:** STRICT READ-ONLY. No DB writes / DDL / migrations / triggers; no CSV / model / ETL / API / UI changes; no data fabrication; no NULL filling; no silent corrections; no inference of absent values. One report file (`plan_25_08/ml_complete_data_forensic_audit_report.md`); all analysis in temp (`C:\Users\HARSHG~1\AppData\Local\Temp\opencode\`), nothing in the repo.
**Scope:** Data + ML dataset reconciliation to decide whether ByteBrain (`D:\KenexAi\ByteBrain`) is safe to retrain M1 / M2 / M3, covering CSE Sem 1–7 and BBA, each field classified ACTUAL / PREDICTED / DERIVED / PLACEHOLDER / SEEDED / MISSING.
**Verdict vocabulary:** `DATA_AUDIT_CLEAN` / `CLEAN_WITH_MINOR_WARNINGS` / `REQUIRES_CORRECTION` / `BLOCKED`.
**ML readiness:** `READY` / `PARTIALLY_READY` / `NOT_READY`.

---

## 1. Executive Summary

The database and the ML dataset snapshots are **out of sync at the live (final) semester for BOTH departments**, and this drift contaminates the training targets/labels of M2 and M3. The live semester rows (CSE-7, BBA-5) must be excluded/NULLed correctly and the ML snapshots re-derived before any retrain.

- **CSE Sem-7 INCOMPLETE** — 349/350 subject end-sem marks NULL; only 1 genuine row (`STU000002`/`SUB0053` = 18+49+25=92, B+, Pass). Live summary was zeroed to `0.0 / PASS / B / backlog 0 / credits_earned 19` for all 50 — a partial, inconsistent placeholder, not NULL/incomplete.
- **BBA Sem-5 INCOMPLETE** — 210 enrolled, **0 end-sem marks**, yet Sem-5 summary is fully populated (PASS=26, ATKT=4, SGPA 1.59–10.00, backlog counts) — fabricated placeholders with no supporting subject marks.
- **ML consumers read CSV snapshots (`ml/data/raw/*_rows.csv`), not the live DB.** Those CSVs still hold the migration-seed fabricated Sem-7 summary (SGPA 7.84 etc.) that the live DB no longer has (live = zeroed). **53 summary rows differ** (50 CSE Sem-7 + 3 STU000002 Sem-4/5/6).
- **`students.latest_sgpa` and `students.total_backlogs` were SEEDED from fabricated live-semester summaries** (Sem-7 for CSE, Sem-5 for BBA), not from the latest completed-semester actuals — a major integrity issue in an academic-profile field.
- **80/420 (19%) M2/M3 training rows carry an invalid T+1 target** (CSE Sem-6 → fabricated Sem-7; BBA Sem-4 → fabricated Sem-5). M3's 28-row positive class (6.7%) is unreliable: STU000032/041 are labelled "at risk" purely from fabricated Sem-7 ATKT with zero supporting end-sem marks.
- **M1 is largely clean but not fully.** Training = `end_sem NOT NULL` = 3,293 rows (CSE 2,453 + BBA 840). The 2 extra fabricated Sem-7 end-sem rows (STU000003/SUB0050, STU000004/SUB0050) and the stale/wrong STU000002 Sem-7 row (SUB0050=40 vs live SUB0053=25) enter training as if real.
- **Prediction write-back is CLEAN** — M2/M3/M4 predictions are appended only to `ml_predictions` (JSONB); nothing is written to `summary` or `students.latest_sgpa` by the runtime pipeline (confirmed in `ml_prediction_repo.py` append-only + `prediction_contract_service.py` read-only). The placeholder `latest_sgpa` comes from the seed migration only.

**FINAL VERDICT: `REQUIRES_CORRECTION`.** ML readiness: **M1 PARTIALLY_READY, M2 NOT_READY, M3 NOT_READY.** Retraining on current snapshots or current live DB is not safe until corrected.

---

## 2. Scope, Sources & Method

**Sources (read-only):**
- Live PostgreSQL (Supabase pooler `aws-1-ap-south-1.pooler.supabase.com:6543`, DB `postgres`) via backend venv + `asyncpg`, `ssl=require`, `statement_cache_size=0`, `default_transaction_read_only=on`, retry loop.
- `ml/data/raw/*_rows.csv` — 17 table snapshots the ML pipeline actually reads (no `ml_predictions_rows.csv`, no `student_row.csv`).
- `supabase_export_all_dataset_backup/*.csv` — 21 files incl. `ml_predictions.csv`, `prediction_feedback.csv`.
- `ml/data/final/m4_career_readiness_scores.csv` (80×28) + `ml/m4_career_readiness_scores.csv`.
- `backend/datasets/daily_attendance_cse_sem7.csv` (646K), `weekly_timetable_cse_sem7.csv`.
- Migrations `03_students_data.sql`, `06_student_semester_summary_data.sql`, `09_risk_predictions_data.sql`, `17_fix_marks_derivation_trigger.sql`, `18_marks_remarks_derivation.sql`, `21_ml_predictions.sql`.
- ETL `backend/etl/stages/derive.py`, `second_cohort.py`, `config.py`, `validation.py`.
- ML `ml/src/m1/data.py`, `m1/config.py`, `m2/data.py`, `features/v1_cohort_dataset.py`, `v1_dataset.py`, `v1_config.py`, `m1/config.py`, `m2/config.py`, `m3/config.py`, `prediction_persistence.py`, `inference.py`, `registry.py`; services `prediction_generation_service.py`, `prediction_contract_service.py`, `ml_prediction_repo.py`.

**Method:** live DB census → CSV↔DB row-key drift per semester/field → dataset-builder trace → in-memory target/label reconstruction → provenance via migrations + ETL → prediction-write-back trace → model artifact hash fingerprint (before/after).

**Model artifact SHA-256 (captured; verified unchanged post-audit):**
| Artifact | SHA-256 |
|---|---|
| `m1_subject_endmarks.joblib` | `3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E` |
| `m2_next_semester_performance.joblib` | `6CAC9A884ABAEF16575D7B866405A726F751BEFC18359C3C599AFDB5E071C012` |
| `m3_next_semester_at_risk.joblib` | `99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7` |

**NO DATABASE OR PROJECT DATA WAS MODIFIED BY THIS AUDIT** (read-only transactions; hash fingerprints identical before and after).

---

## 3. Live Database Census (verified, read-only)

| Table | Rows |
|---|---|
| students | 80 (CSE 50, BBA 30) |
| student_subject_enrollment | 3,850 |
| student_subject_performance | 3,850 |
| student_semester_summary | 500 (CSE 350 + BBA 150) |
| attendance | 3,850 (CSE 2,800 + BBA 1,050) |
| daily_attendance_07 | 6,250 (CSE-only granular source) |
| weekly_timetable_07 | 15 |
| ml_predictions | 5,072 |
| risk_predictions | 80 (legacy seeded statuses; NOT M3) |
| prediction_feedback | (exists; counts per backup) |

**Attendance is NOT CSE-only.** Attendance has both CSE (2,800) and BBA (1,050) aggregate rows at subject×student×semester grain. `daily_attendance_07` (the fine-grained lecture roll, 6,250 rows) is CSE Sem-7 only; BBA has no daily-lecture rows. So BBA has aggregate attendance Sem 1–5 but no live daily attendance feed.

---

## 4. CSV / Snapshot Inventory

- **`ml/data/raw/*_rows.csv` (17)** — the training/deployment inputs to M1/M2/M3: `students_rows`, `student_subject_enrollment_rows`, `student_subject_performance_rows`, `attendance_rows`, `subjects_rows`, `student_semester_summary_rows`, `departments_rows`, etc.
- **`Student_row.csv` — DOES NOT EXIST** anywhere in the project (confirmed via glob + dedicated search). No file of that name; the corpus uses `students_rows.csv` / `student_rows.csv` under `ml/data/raw/`. Any workflow referencing `Student_row.csv` must be pointed at `students_rows.csv`.
- **No pre-materialized M1/M2/M3 dataset CSVs exist** — M1/M2/M3 build their datasets in-memory from `ml/data/raw/*_rows.csv` at train/inference time. Only M4 has a materialized artifact (`ml/data/final/m4_career_readiness_scores.csv`, 80×28).
- **`supabase_export_all_dataset_backup/*.csv`** — older all-table export (incl. `ml_predictions.csv`, `prediction_feedback.csv`); its summary Sem-7 is zeroed (matches live DB, not `ml/data/raw`).

---

## 5. Students / ID Reconciliation

- 80 students across all sources; **no missing / duplicate / orphan IDs** across `students` (DB), `students_rows.csv` and every flat CSV.
- Admissions: all 80 `admission_year` 2023 (CSE 50 + BBA 30).
- "Duplicated sid" counts are normal one-to-many row grain: summary 500, performance=enrollment=attendance=3,850, daily_attendance_07=6,250.

---

## 6. CSE Summary — Field-by-Field Classifications (Sem 1–7)

Based on live DB reconstrucibility (summary vs subject-marks SGPA recompute) and provenance:

| Field | Sem 1–6 (CSE, completed) | Sem 7 (CSE, live) |
|---|---|---|
| semester_no | ACTUAL | ACTUAL |
| academic_year | ACTUAL | ACTUAL |
| subjects_registered / credits_registered | DERIVED (match subject counts) | DERIVED (19/19, but live) |
| semester_total_marks / semester_percentage | DERIVED (matches subject sums) | **PLACEHOLDER (0.0)** |
| semester_sgpa | **DERIVED_FROM_ACTUAL** (297/300 match recalc; 3 drift = STU000002 Sem4/5/6) | **PLACEHOLDER (0.0)** |
| semester_grade | DERIVED (B for all) | **PLACEHOLDER (B)** |
| semester_result | DERIVED (PASS 48, ATKT 2) | **PLACEHOLDER (PASS 50)** |
| backlog_count | **DERIVED/CONFIRMED** (0 vs subject fails across all 300 rows) | **PLACEHOLDER (0)** |
| credits_earned | DERIVED (== registered 48/50; 2 ATKT students differ) | **PLACEHOLDER (19=19)** |
| semester_attendance_percentage | DERIVED | ACTUAL (attendance exists) |

`semester_sgpa` Sem 1–6 recompute = Σ(grade_point×credits)/Σcredits with Fail grade_point=0; stored matches 297/300 (99%); only STU000002 Sem4/5/6 drift (stored 9.23/9.62/9.99 vs recalc 10.0; CSV also shows 10.0) — a real recording drift, present in both DB and CSV.

---

## 7. CSE Sem-7 Deep Audit (subject grain)

- internal_marks 350/350 present; mid_sem_marks 350/350 present; **end_sem_marks 1/350** (`STU000002`/`SUB0053` = 18+49+25=92, B+, Pass — internally consistent).
- Trigger correctness: **0 flags** where `end_sem NULL` yet `total/grade/result NOT NULL` at subject level → `17_fix_marks_derivation_trigger.sql` (`trigger_update_performance` → `trg_calculate_performance`, BEFORE INSERT/UPDATE on `student_subject_performance`) correctly leaves subject derived fields NULL when incomplete.
- **Contradiction:** subject level is correctly NULL for 349/350, but summary level carries 50/50 populated placeholder rows. The trigger fixes subject performance only; it does NOT fix `student_semester_summary`.

**Hard invariant for CSE Sem-7 actuals: SGPA / percentage / grade / result / backlog = NULL** (not 0 / not PASS / not B); only attendance is real.

---

## 8. BBA Structural Audit

- 30 BBA students; performance 1,050 (210/sem × 5), attendance 1,050 (Sem 1–5), internal+mid marks 210/210 per Sem 1–5.
- **BBA end_sem marks: Sem 1–4 = 210/sem (840 total); Sem 5 = 0/210.**
- BBA summary: Sem 1–4 DERIVED; **Sem 5 fabricated** — 30 rows, PASS=26, ATKT=4, SGPA>0 for all 30 (1.59–10.00) with zero end_sem marks.

**BBA hard invariant: Sem-5 SGPA/percentage/grade/result/backlog = NULL** (in-progress live semester), matching CSE Sem-7.

---

## 9. CSV ↔ Database Reconciliation (row-key drift)

Grain: (student, semester). DB = live; CSV = `ml/data/raw/student_semester_summary_rows.csv`; backup = `supabase_export_.../student_semester_summary.csv`.
- Sem 1–3: perfect.
- Sem 4/5/6: 1 row each — `STU000002` SGPA CSV=10.0 vs DB=9.23/9.62/9.99.
- **Sem 7: sgpaAgree 0/50, percAgree 0/50, resultAgree 48/50, backlogAgree 48/50.** CSV holds the fabricated migration-seed Sem-7 values (e.g. STU000001 7.84, STU000032 2.89, STU000041 3.42); DB holds zeroed placeholders.
- Backup `student_semester_summary.csv` Sem-7 = 0.00/PASS — matches **DB**, not `ml/data/raw`.
- **Total differing summary rows = 53** (50 Sem-7 + 3 STU000002 Sem4-6).

Performance Sem-7 drift (grain student×subject): CSV end_sem.notna=3 (STU000002/SUB0050=40, STU000003/SUB0050=40, STU000004/SUB0050=45) vs DB=1 (STU000002/SUB0053=25). **CSV's STU000002 Sem-7 subject row is a different (wrong) subject+mark than the live genuine row.**

---

## 10. Prediction Separation (ML outputs vs actuals)

- `ml_predictions` (5,072) stores **forward-looking predictions only** in JSONB `prediction_value` (e.g. M2 of Sem-7 → predict Sem-8 = 6.25 / 57.51). Model-specific field `prediction_type` / `model_version` / `generated_at`.
- **Runtime never writes predictions into `student_semester_summary` or `students.latest_sgpa`.** `ml_prediction_repo.py` is append-only (`INSERT INTO ml_predictions` only); `prediction_contract_service.py` docstring: "NEVER writes predictions back to the database, NEVER persists" (read-only); `prediction_generation_service.py` → `persist_predictions` → `ml_predictions`.
- `faculty_repo.py` UPDATEs to `student_semester_summary`/`students` are the ETL/derivation path (academic derived fields), not the ML prediction path.
- Conclusion: **no prediction leakage into academic-profile fields.** The placeholder `latest_sgpa` / `total_backlogs` come from the seed migration (Section 12), not from M2.

---

## 11. latest_sgpa Audit

`students.latest_sgpa` was SEEDED (`03_students_data.sql`) with the **fabricated live-semester summary SGPA**, not the latest completed actual:
- **CSE:** STU000001 latest=7.84 = CSV-fabricated Sem-7 (sem-6 actual 7.77); STU000032 latest=2.89 = fabricated Sem-7 (sem-6 actual 3.64); STU000041 latest=3.42 = fabricated Sem-7 (sem-6 actual 4.32).
- **BBA:** STU000052 latest=1.59 = Sem-5 (1.59); STU000060=1.59 = Sem-5; STU000064=2.73 = Sem-5; STU000075=2.73 = Sem-5.
- `latest_sgpa` == Sem-6 actual for only **35/50** CSE; matches Sem-5 for 16, Sem-6 for 15, overall_cgpa for 12 — i.e. **arbitrary / seed-driven**.

**Conclusion: `latest_sgpa` is PLACEHOLDER/SEEDED (fabricated live-semester), NOT latest-completed actual.** It is excluded from M1/M2/M3 features (forbidden) but is served as a headline academic field to UIs/analytics — a data-integrity concern independent of the models.

---

## 12. Backlog Reconstruction Audit

- **`summary.backlog_count`, CSE Sem 1–6: CONFIRMED derivable** — 0 rows differ vs subject fail counts across all 300 completed rows.
- **`students.total_backlogs` is WRONG/unreliable:** STU000032=24 (subject fails=21, Σsummary=21), STU000041=25 (fails=23, Σ=23), STU000017=1 (fails=0, Σ=0). Seed value ≠ subject-derivable count.
- CSE `total_credits_registered`=159 for all (= Σ Sem1-7); `total_credits_earned`=159 except STU000032 (91, failed 68) and STU000041 (88, failed 71) — internally consistent with failed credits, but only the 2 special students reflect it.

---

## 13. M1 Dataset Definition

Source: `m1/data.py`, `m1/config.py` (reads performance+attendance+subjects+students+summary CSVs).
- Grain: (student, subject, semester); join = performance INNER JOIN attendance on `enrollment_record_id` (1:1) + LEFT subjects/students.
- Target: `end_sem_marks`. **Training = end_sem NOT NULL; deployment = end_sem NULL.**
- Features (baseline): `internal_marks`, `mid_sem_marks`, `attendance_percentage`, `subject_type`, `credits`, `semester_no`, `department_name`, `gender`. Forbidden include `latest_sgpa`, `total_backlogs`, `overall_*`, `total_marks`, `grade`, `result_status`.
- **M1 trains on BOTH departments** (CSE 2,453 + BBA 840 = 3,293; deploy 557).
- **Contamination:** Sem-7 CSV rows with end_sem present = 3 (STU000002/SUB0050=40 [wrong value/subject vs live], STU000003/SUB0050=40, STU000004/SUB0050=45) enter training as real. These are fabricated/stale → **remove before retrain**.
- Verdict: PARTIALLY_READY (contamination limited to 3 rows, all at the stale live semester; genuine Sem 1–6 blocks are sound).

---

## 14. M2 Dataset Definition

Source: `m2/data.py` → `student_semester_summary_rows.csv` + `students_rows.csv`; V1 builder (`v1_cohort_dataset.py`, `v1_dataset.py` / `v1_label_builder.py`).
- Grain: 1 row = 1 student at 1 completed semester.
- Task: predict next-semester `semester_percentage` / `semester_sgpa`.
- 11 V1 features (from `v1_config.py`): `semester_no, subjects_registered, credits_registered, credits_earned, semester_total_marks, semester_percentage, semester_sgpa, semester_attendance_percentage, backlog_count, department_name, gender`. Forbidden incl. `latest_sgpa, overall_cgpa, total_backlogs, semester_result` (shifted to target).
- Total 500; **training 420** (CSE 300 + BBA 120); **deployment 80** (CSE Sem-7 50 + BBA Sem-5 30).
- **T+1 contamination: 80/420 (19%)** — the last training row per student is CSE Sem-6 (50) + BBA Sem-4 (30), whose T+1 target is the **fabricated Sem-7 / Sem-5** summary value (e.g. STU000001 next_sgpa 7.84 / next_pct 72.86 from CSV).
- Verdict: **NOT_READY** — 19% invalid training targets, plus deployment features are fabricated placeholders.

---

## 15. M3 Dataset Definition

Source: same V1 builder + `m3/config.py`.
- Task: binary `is_at_risk_next_sem` from shifted `semester_result`/`backlog_count`; features identical to M2 (11 V1 features).
- Training 420; **positive class 28/420 (6.7%)**, highly imbalanced.
- **Labels unreliable:** STU000032 & STU000041 are "at risk" in the CSV from a fabricated Sem-7 ATKT/backlog with **zero supporting end-sem marks** → the positives include two label-only-from-placeholder rows dropped from the live DB. Underpowered positive class + label contamination.
- Verdict: **NOT_READY / BLOCKED** (also previously blocked for underpowered positive class).

---

## 16. Derived-Field / Trigger Logic

- Single DB trigger: `trigger_update_performance` → `trg_calculate_performance` on `student_subject_performance` (BEFORE INSERT/UPDATE). It computes subject `total_marks/percentage/grade/grade_point/result_status` only when `internal + mid + end` are complete (verified 0 partial-flag rows).
- **It does NOT update `student_semester_summary` or `students`.** Hence the stale/fabricated summary and `latest_sgpa` persist (ETL `_derive_semester_summary` in `backend/etl/stages/derive.py` writes `0.0/PASS/B/backlog0/credits_earned=credits_registered` for the live semester; does not NULL it).
- `18_marks_remarks_derivation.sql` mirrors subject-level derivation; no summary/students trigger exists.

---

## 17. Contamination / Severe Issues (ranked)

| # | Severity | Issue |
|---|---|---|
| 1 | CRITICAL | `students.latest_sgpa` & `total_backlogs` = SEEDED fabricated live-semester values (CSE Sem-7 / BBA Sem-5), not latest-completed actuals. |
| 2 | CRITICAL | `ml/data/raw/*.csv` summary Sem-7 = fabricated migration-seed; live DB = zeroed; 53 summary rows differ; training snapshots stale. |
| 3 | CRITICAL | M2/M3: 80/420 (19%) training rows carry invalid T+1 target from fabricated/incomplete next-semester. |
| 4 | HIGH | M3 positive class 28/420 (6.7%); 2 positives (STU000032/041) label-only from fabricated Sem-7 ATKT with 0 end-sem marks. |
| 5 | HIGH | `student_semester_summary` for live sems (CSE-7, BBA-5) carries inconsistent placeholder (0.0/PASS/B/backlog0) instead of NULL. |
| 6 | MEDIUM | M1: 3 stale/fabricated Sem-7 end-sem rows (STU000002/003/004) enter training; STU000002's is wrong subject+value. |
| 7 | MEDIUM | STU000002 Sem 4/5/6 SGPA drift (DB 9.23/9.62/9.99 vs recalc/CSV 10.0). |
| 8 | MEDIUM | `students.total_backlogs` mismatch (STU000032/041/017) vs subject-fail / summary counts. |
| 9 | LOW | BBA has no daily-attendance feed (only aggregate Sem 1–5). |

---

## 18. Correction Plan

- **A (data model, required first):** NULL out summary + `students.latest_sgpa`/`overall_*`/`total_backlogs` for CSE Sem-7 and BBA Sem-5 (set to NULL for genuinely incomplete). Fix STU000002 Sem 4/5/6 SGPA to recomputed 10.0. Recompute `total_backlogs` from subject-fail counts. Re-seed `latest_sgpa` = latest completed-semester actual SGPA.
- **B (snapshots):** after A, re-derive `ml/data/raw/*_rows.csv` from the corrected DB (drop 3 Sem-7 M1 rows; deployment-only for CSE-7/BBA-5 in M2/M3).
- **C (retrain gate):** re-train M1 after B (expect 2,453+840-3 rows); re-build M2/M3 training = only Sem ≤ live-1 (drop the 80 T+1 rows; M3 positives = real subject-fail-based backlogs only). Re-balance M3 or gate on positive-class sufficiency.
- **D (pipeline fix):** trigger/ETL must NULL (not zero/PASS) live-semester summary; add a summary/`students` recompute on semester completion; block prediction snapshots until completion.
- Order A → B → C → D. Re-run this audit to confirm 0 contamination before any retrain.

---

## 19. Final Verdict & ML Readiness Decision

**FINAL VERDICT: `REQUIRES_CORRECTION`** (previous run `REQUIRES_CORRECTION`; unchanged).

| Model | Readiness | Reason |
|---|---|---|
| M1 | **PARTIALLY_READY** | Sound on Sem 1–6; remove 3 stale Sem-7 rows then retrain. |
| M2 | **NOT_READY** | 80/420 (19%) invalid T+1 targets; deployment features fabricated. |
| M3 | **NOT_READY (BLOCKED)** | Label contamination + underpowered positive class. |

**Data integrity status:** LIVE semesters (CSE-7, BBA-5) must be NULL (attendance real, academic outcomes absent), not 0/PASS/B. `students.latest_sgpa`/`total_backlogs` are seeded placeholders and must be re-derived. Predictions (M1–M4) are correctly isolated in `ml_predictions`; no prediction leaks into academic-profile fields.

**Read-only guarantee:** NO DATABASE OR PROJECT DATA WAS MODIFIED BY THIS AUDIT. Model artifacts bit-identical (SHA-256 unchanged) — no retraining performed.

---

*Footer: STRICT READ-ONLY audit — no DB writes/DDL/migrations, no CSV/model/ETL/API/UI changes, no data fabrication, no NULL filling, no silent corrections, no treatment of M2 predictions as actual outcomes. Analysis scripts under `C:\Users\HARSHG~1\AppData\Local\Temp\opencode\`.*
