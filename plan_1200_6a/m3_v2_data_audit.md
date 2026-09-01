# M3 v2 — Data Audit Report

**Audited:** 2026-09-01 (live read-only Supabase probe; read-only multi-table audit)
**Cohort:** CSE 6A — 1,200 students (STU6A0001..STU6A1200)
**Scope:** M3 At-Risk Student Prediction (binary risk of entering an academic-risk state in the NEXT semester, T+1)
**Temporal contract:** Features from observation semester **T** only; label computed from academic outcomes in semester **T+1**. No T+1 outcome may enter `X`.

---

## 1. Prior M3 State (Legacy)

The legacy M3 (`ml/src/m3/`, plus `ml/src/features/v1_*`) is **BLOCKED** in production. Key facts:

- **Canonical legacy target (valid contract):** `semester_result(T+1) IN ('FAIL','ATKT') OR backlog_count(T+1) > 0`.
- Legacy M3 was trained on the **80-student cohort** (CSE 50 + BBA 30; STU000001..STU000080, admission year 2023).
- Validation gate **FAIL**: only **6 positive students** (26 positive rows); ≥1 GroupKFold fold had 0 positives; perfect informative-fold metrics flagged as small-sample artifact.
- `retrain_m3.py` is **unsafe** (divergent `sgpa<4.0` rule, `StratifiedKFold` instead of `GroupKFold`, schema alias mismatch) — permanently blocked by `plan_1200_6a/existing_ml_audit.md`.
- Legacy artifact `ml/artifacts/models/m3_next_semester_at_risk.joblib` persisted but unused.
- Backend M3 future-risk predictions (`admin_ml_service.py` reading `ml_predictions` table) are historical/legacy only.
- The analytic `at_risk` API (attendance<75 / backlogs>=2 / SGPA<6 rules) is a **different, deterministic, non-predictive** concept and is NOT M3.

**M3 V2 decision:** The 1200-cohort has NOT been used for M3. Building M3 V2 on it is a from-scratch, real-data rebuild with a materially larger and valid positive class (verified below).

---

## 2. Data Sources Audited (Live Supabase, 6A) — Read-Only

| Table | 6A Rows | Used for M3 V2 (T features) |
|---|---|---|
| `students` | 1,200 | Yes (gender, current_semester) |
| `student_semester_summary` | 9,600 | **Yes — primary** (T outcomes + T+1 label source) |
| `student_subject_performance` | 68,400 | Yes (T subject aggregates) |
| `student_subject_enrollment` | 68,400 | Yes (T subject/credit load) |
| `attendance_weekly` | 547,200 | Yes (T weekly attendance aggregates) |
| `student_learning_activity` | 547,200 | Yes (T engagement aggregates) |
| `student_lifestyle_survey` | 9,600 | Yes (T survey: stress, study hours) |
| `faculty_student_map` | 1,280 | No (mentor assignment; used for RBAC only) |
| `student_skill_profile` / `career_preferences_v2` / `placement` | — | **Excluded** (no semester anchor / future / placement leakage by rule) |

---

## 3. Label-Source Columns (Raw, Verified Read-Only)

`student_semester_summary` carries the exact label-source columns:

- `semester_result` — value distribution (all 9,600 rows): `PASS` 9,373, `ATKT` 227, **`FAIL` 0**.
- `backlog_count` — value distribution: 0 (9,373), 1 (221), 2 (6); max = 2.

**Critical equivalence (this cohort):** every `semester_result == 'ATKT'` row (227) has `backlog_count > 0` (227), and vice-versa; no row has `backlog>0` with a `PASS` result and no `FAIL` value exists. Therefore the canonical risk rule
`semester_result(T+1) IN (FAIL, ATKT) OR backlog_count(T+1) > 0`
reduces, in this cohort, to **`backlog_count(T+1) > 0`** (equivalently `semester_result(T+1) == 'ATKT'`).

By meaningful academic semester (all 6A):

| Sem | ATKT / backlog>0 | n |
|---|---|---|
| 1 | 27 | 1200 |
| 2 | 34 | 1200 |
| 3 | 56 | 1200 |
| 4 | 35 | 1200 |
| 5 | 26 | 1200 |
| 6 | 21 | 1200 |
| 7 | 28 | 1200 |
| 8 | **0** | 1200 | (internship; all PASS, 1 subject) |

Semester 8 is the final internship term with 0 at-risk events — it is excluded as a target (consistent with M2 V2's sem-8 boundary).

---

## 4. At-Risk Label Reality Check (7200 eligible transitions, T=1..6 → T+1=2..7)

| Candidate target | Positive | Total | Rate | At-risk students |
|---|---|---|---|---|
| **D1 canonical** (result∈{FAIL,ATKT} OR backlog>0) | **200** | 7,200 | **2.78%** | **165** |
| D2 backlog increase (T+1 > T) | 182 | 7,200 | 2.53% | 163 |
| D3 any backlog at T+1 | 200 | 7,200 | 2.78% | 165 |
| D5 result∈{FAIL,ATKT} | 200 | 7,200 | 2.78% | 165 |
| D4 SGPA drop > 0.5 | 443 | 7,200 | 6.15% | 375 |

**Decisive:** the 1200-cohort positive class (200 rows / 165 distinct students) is **33× larger** than the legacy 6-student cohort. GroupKFold folds will not collapse into the legacy "few repeating students memorization" artifact.

Positive rate by observation semester T (canonical D1):

| T | T+1 | pos/n | rate |
|---|---|---|---|
| 1 | 2 | 34/1200 | 2.83% |
| 2 | 3 | 56/1200 | 4.67% |
| 3 | 4 | 35/1200 | 2.92% |
| 4 | 5 | 26/1200 | 2.17% |
| 5 | 6 | 21/1200 | 1.75% |
| 6 | **7** | 28/1200 | **2.33%** (temporal holdout) |

Per-student event count (D1): 0 events → 1,035 students; 1 → 132; 2 → 31; 3 → 2. The at-risk population is **spread across many students**, not a handful of repeat offenders — a healthy, non-degenerate learning signal.

---

## 5. Temporal Target Construction (Phase C)

Grain: `(student_id, observation_semester T)`. Target from semester T+1 = T+1.
- Transitions built by within-student forward shift (`shift(-1)`) on `semester_result` / `backlog_count`.
- **Training transitions:** T = 1..5 (rows = 6,000; targets semesters 2..6).
- **Temporal holdout:** T = 6 (rows = 1,200; target semester 7) — 28 positives. Semester 7 excluded from training.
- **Restricted to normal academic T+1 ∈ {2..7}** — excludes the degenerate internship transition T=7→8 and the final T=8 (no T+1).
- Validations: T < T+1, T+1 = T+1, no grain duplicates, no cross-student/cross-cohort joins, no missing target for expected transitions (all 7,200 rows have a target).

---

## 6. Feature-Source Availability at Observation T (Point-in-Time)

All feature sources carry T-grainless data joinable to `(student_id, semester_no)`; identical loading as M2 V2 (`SupabaseLoader`). Available T features: current SGPA/percentage/marks, subject performance aggregates (mean/σ), weekly attendance aggregates, learning-activity aggregates, backlog trajectory (current, previous, change, cumulative), lifestyle (stress/study hours), gender, credits/workload, subject count.

**Strictly excluded from X (T+1 / future / placement):** T+1 semester_sgpa/percentage/grade/result/backlog/attendance/learning; any `_t1/_lag1/_next` derived column; `placement_*`; `package_*`. T+1 data appears ONLY in `y`.

---

## 7. Data Quality Summary

| Dimension | Rating | Notes |
|---|---|---|
| Completeness | EXCELLENT | 7,200/7,200 transitions have a valid T+1 target; only expected sem-1 temporal-feature nulls |
| Label source integrity | EXCELLENT | `semester_result` clean (PASS/ATKT), backlog 0–2, no FAIL value, ATKT ⟺ backlog>0 |
| Class balance | ~2.8% positive | Imbalanced — requires leakage-safe imbalance handling (class_weight/threshold), NOT naive global oversampling |
| Grain | CORRECT | `(student_id, semester_no)` unique per summary row |
| Protection from leakage | CONTROLLABLE | explicit T-only vs T+1 separation; sem-1 drift/prior nulls need imputation |
| Freshness | CURRENT | current ETL of the canonical 1200 6A cohort |

---

## 8. Impact on Later Phases

- **Phase B:** select the legacy canonical target `result(T+1)∈{FAIL,ATKT} OR backlog(T+1)>0` (= `backlog(T+1)>0` in this cohort); param class_weight=balanced; recall-focused but threshold-tuned on validation.
- **Phase H:** temporal holdout T=6→7 (28 positives) + GroupKFold by `student_id` (5-fold × seeds).
- **Phase U:** full metric suite (precision/recall/F1/AUC/PR-AUC/CM/specificity/balanced-acc), Brier, calibration.
- **Deployment boundary:** current cohort at semester 8 has no T+1 → endpoint returns `NO_DATA` for those students; serves any student with an upcoming normal semester.