# M1 V2 — Zero-Prediction Root-Cause Investigation & Fix

**Date:** 2026-09-01
**Severity:** URGENT production bug
**Area:** M1 V2 Subject End-Semester Prediction
**Status:** ❌ Bug **RESOLVED** (fix + tests shipped)

---

## 1. Symptom

For student **Aarav Patel** (`STU000002`, enrollment `2023010002`, admission 2023,
CSE, current semester 7), the M1 V2 subject prediction card showed, for **every**
Sem-7 subject:

- `predicted_end_sem_marks = 0.0 / 70`
- `grade_band = F`, `grade_label = "At Risk"`
- label **At Risk** (via the 0.0 threshold)

Additionally, M4 Career Readiness showed:
> "Declining academic trend (from 95.8% to 0.0%)"

---

## 2. Exact reproduction (read-only, live Supabase)

Ran a read-only inference probe through the real artifact + real DB:

| student | cohort | `readiness_status` | subjects | `pre_endsem_assessment_pct` |
|---|---|---|---|---|
| `STU000002` (Aarav) | legacy `STU00` / 2023 | READY | all 7 → **0.0 / 70, F, At Risk** | `None` (→ coerced to 0.0) |
| `STU6A0001` | 6A | READY | 1 → 42.63, A | present (e.g. 60–82) |
| `STU6A0002`/`0003`/`0100`/`0600`/`1200` | 6A | READY | 42.6–56.2 | present |

Backend raw feature vector for Aarav Sem-7 subjects:
`internal_marks=19, mid_sem_marks=50, att_total_pct=None, pre_endsem_assessment_pct=0.0`
(pre-exam composite NULL → coerced to 0; `attendance_weekly` empty; `student_learning_activity` empty).

The backend route `/predict/m1v2/{id}` returned **200** with these 0.0 results
(it only 404s when the subject set is empty). The frontend renders exactly what
the backend returns (`m1v2-card.tsx` prints `predicted_end_sem_marks.toFixed(1)`)
— the frontend is **faithful and not the bug source**.

---

## 3. First point where the 0.0 appears

**Feature-assembly in `ml/v2/m1_subject_prediction/inference/predictor.py`
`M1V2Predictor.predict_for_student`.** Two compounding defects:

1. **No deployment-cohort guard.** The predictor ran inference for *any* student
   with `student_subject_performance` rows — including out-of-distribution legacy
   `STU00` students — despite the model being trained/validated only on the
   `CSE_6A_1200`/`STU6A` cohort (artifact metadata + `config.COHORT_ID_PREFIX`).
2. **NULL → 0 silent coercion.** `float(prow.get("pre_endsem_assessment_pct") or 0)`
   (and equivalent for internal/mid_sem/assignment/quiz) silently turns the
   missing V2 feature sources of the legacy cohort into **0**. The legacy student
   then gets a near-all-zero, out-of-distribution vector; the ridge model clips
   the output to `TARGET_MIN = 0.0`, which `_grade_from_marks` maps to **F / At Risk**.

The model artifact is **not** the cause. The training/holdout math is **not** the
cause. The frontend is **not** the cause.

---

## 4. Root cause (summary)

> M1 V2 was deployed to the **CSE 6A (STU6A) cohort**. Aarav belongs to the
> **legacy 2023 `STU00` cohort** whose `student_subject_performance` rows lack the
> V2 feature sources (`pre_endsem_assessment_pct`, assignment, quiz, submission
> delay, `attendance_weekly`, `student_learning_activity`). Because the predictor
> had **no cohort guard** and coerced missing signals to **0**, the legacy student
> was scored by an out-of-distribution model, producing the false `0.0/70 F`.

---

## 5. M4 contamination verdict: **NO**

Traced `ml/m4_career_readiness.py` and `ml/src/m4/engine.py`. The M4 academic
trend (`first/last_semester_percentage`) is computed from **actual
`student_semester_summary.semester_percentage`**, an entirely separate table from
the M1 prediction. Live read-only probe confirmed Aarav's real
`student_semester_summary` has `semester 7 → semester_percentage=0.00,
semester_sgpa=0.00, semester_result=PASS` (a data-quality artifact in the legacy
summary: a semester recorded as 0% but result PASS).

**M1 predictions do NOT feed M4.** The "0.0%" in M4 is a real (bad) recorded value,
not a leaked/contaminated prediction. **No M4 code change is warranted by this bug.**
M4 academic-trend behavior is left unchanged.

---

## 6. Fix (smallest correct, root-cause)

Applied to `ml/v2/m1_subject_prediction/inference/predictor.py` only:

1. **Deployment cohort guard** (primary): after fetching the student row, if
   `student_id` does not start with the deployment prefix
   (`artifact metadata["student_prefix"]` or `config.COHORT_ID_PREFIX`,
   i.e. `STU6A`) → return a structured **NO_DATA** payload with an explicit reason.
   This triggers the existing service `_guard_readiness` → **HTTP 404**, which the
   frontend already renders as an honest "Not available yet" state
   (`page.tsx isNoData`). **A fabricated 0.0 can no longer be produced for
   out-of-cohort students.**
2. **Missing pre-exam signal guard** (hardening of the flagged "0 for missing
   data" fault): within the deployment cohort, a subject whose
   `pre_endsem_assessment_pct` is NULL/NaN is **skipped** (not predicted as 0);
   if no subject remains, readiness becomes NO_DATA. STU6A subjects all carry this
   signal, so the 6A cohort is unaffected.

No model retrain. No changes to M2/M3/M4 logic. The validated M1 V2 artifact is
preserved and unchanged. **Supabase is read-only and unchanged** (all probes were
SELECT-only).

**Files changed:**
- `ml/v2/m1_subject_prediction/inference/predictor.py` — cohort guard + missing pre-exam skip.
- `backend/tests/test_m1v2_prediction.py` — added `TestDeploymentCohortGuard` (5 new tests).

---

## 7. Verification

Read-only, live-DB after fix:

| student | before | after |
|---|---|---|
| `STU000002` (Aarav) | `0.0/70 F At Risk` (200) | **NO_DATA (404)**, reason mentions out-of-cohort |
| `STU6A0001` | 42.63 A (200) | 42.63 A (200) — unchanged |

**Levels verified:**
- Predictor (live DB): Aarav → NO_DATA; STU6A0001 → READY 42.63 A.
- Service (live DB): Aarav raises `ValueError` → 404; STU6A → READY.
- HTTP / unit (fake DB): 404 for `STU000002`; 200 for `STU6A0001`.

**Test suites (all green):**
- Backend M1 V2: **35 passed** (`test_m1v2_prediction.py`)
- Backend V2 bundle (M1+M2+M3): **99 passed**
- ML V2 (all M1/M2/M3): **128 passed**
- Full ML suite: **841 passed**
- Frontend: **161 passed**; `tsc --noEmit` clean

---

## 8. Regression tests added

`backend/tests/test_m1v2_prediction.py` → `TestDeploymentCohortGuard`:
- `test_out_of_cohort_student_is_no_data_not_zero` — legacy `STU00` id with real
  performance rows is NO_DATA/404, never 0.0.
- `test_in_cohort_student_is_ready` — `STU6A0001` still READY.
- `test_http_out_of_cohort_is_404` — full FastAPI route → 404.
- `test_in_cohort_missing_pre_exam_signal_is_no_data_not_zero` — cohort subject
  with NULL pre-exam is NO_DATA, not 0.
- `test_in_cohort_subject_missing_signal_is_skipped_others_kept` — partial gap
  excludes only the gapped subject; the rest predict (no zero).

---

## 9. Final status codes

- **M1 V2:** `FIXED`
- **0.0 BUG:** `RESOLVED`
- **NO_DATA:** `CORRECT` (out-of-cohort + missing-signal now map to the honest
  NO_DATA/404 boundary; STU6A predictions unaffected)
- **M4 CONTAMINATION:** `NO` (no change made; verified M1 does not feed M4)
- **FACULTY:** `PASS` (faculty consumes the same `/predict/m1v2` route + service;
  identical math and guard → parity by construction)
- **SUPABASE:** `UNCHANGED` (read-only investigation)