# M1/M2/M3 V2 Production UI Integration Report

- **Task:** Final ML cleanup + phases 2–12 production-quality UI integration of M1 V2, M2 V2, and
  M3 V2, honoring the Phase 3 human-friendly contract (never display raw ML numbers untruthfully,
  never fabricate confidence/signals, distinguish "model estimate" from fact).

## 1. Active UI is now V2-only (student + faculty)

The student grid (`components/student/ml-insights/ml-insights-grid.tsx`) and faculty grid
(`components/faculty/ml-insights/faculty-ml-insights-grid.tsx`) now render the V2 cards
(M1 V2, M2 V2, M3 V2) plus M4 cards. Legacy M1/M2/M3 cards were removed and deleted. The M4
career/readiness surface is preserved.

## 2. M1 V2 (Subject Marks Prediction) — production UI
- Student + faculty cards render each subject's predicted end-sem marks, grade band, and grade label.
- **Genuine defect fixed:** `m1V2GradeTone` previously matched legacy-style band names
  ("Top Performer"/"Above Average"/"Average"/"Below Average"), but the M1 V2 backend derives
  `grade_band` as the grade **letter** (O / A+ / A / B+ / B / C / F) via
  `ml/v2/m1_subject_prediction/inference/predictor.py:_grade_from_marks`. As a result every grade
  rendered destructive (red). Re-mapped to: O/A+/A/B+ → success, B → secondary, C → warning,
  F → destructive. Faculty attention badge now flags C/F instead of the non-existent legacy names.
- Grounded "Signals considered by the model": attendance (`att_total_pct`) and pre-end-semester
  assessment (`pre_endsem_assessment_pct`) are shown only when present for that subject —
  no invented signal list. The interpretation line restates the model estimate (predicted marks /
   max) with the grade label, phrased as an estimate, not a result.

## 3. M2 V2 (Next-Semester Performance) — production UI
- Clear **current-vs-next distinction** added via the backend's semesters
  (`observation_semester` → `prediction_takes_effect_semester`). Labels now read "Predicted SGPA /
  Percentage · Semester {T+1}", and an interpretation block states: "Based on the student's
  completed Semester {T}, the model estimates performance in Semester {T+1}." This makes explicit
  that the figure is a next-semester **model estimate**, not the current result.
- Badge-toned SGPA via `m2V2SgpaTone`. NO_DATA handled (below).

## 4. M3 V2 (At-Risk Prediction) — production UI + validation
- **LOW/MODERATE/LOW-MODERATE/HIGH risk LEVELS** added via `riskLevelLabel` (derived deterministically
  from the model's `probability_at_risk`): High ≥ 0.5, Moderate ≥ 0.3, Low-moderate ≥ 0.15, Low < 0.15.
  Wording is "Estimated risk", never "will fail". The decision threshold and `is_estimated_at_risk`
  are surfaced transparently.
- Grounded, **per-student** contributing signals are shown from the backend `signals` array only
  when a signal actually exists for that student.
- A "Recommended next steps" block (general suggestions, explicitly labelled "not a diagnosis").
- Version: **FURTHER VALIDATION REQUIRED** — 28 positive examples, same-cohort holdout only. The
  report/board must keep this FURTHER VALIDATION REQUIRED marker; the UI does not inflate confidence.

## 5. NO_DATA / no future-semester boundary (deployment boundary)
- Backend returns **404** for M1/M2/M3 NO_DATA, incl. the current cohort at the final/internship
  semester 8 with no upcoming NORMAL academic semester (validated in
  `backend/tests/test_m2v2_prediction.py` and `test_m3v2_prediction.py`:
  `test_http_404_for_final_sem_no_upcoming`).
- Frontend now distinguishes NO_DATA (404) from a real failure (503/network) and renders an honest
  **no-data state**: "A next-semester prediction is not available because a future academic
  semester is not currently available in the dataset." The same pattern is applied to M1
  (subject-level) and M3 (risk-estimate) with truthful wording. Implemented in both pages
  (`app/student/ml-insights/page.tsx`, `app/faculty/.../ml-insights/page.tsx`) and both grids.

## 6. Admin ML analytics — honesty
- No validated cohort/aggregate ML analytics endpoint exists (V2 is per-student only). The admin
  `AcademicPredictionCard` shows explicit availability notices ("not yet available") and renders
  `—` / empty states instead of fabricated cohort statistics. No unvalidated cohort figures.

## 7. RBAC
- V2 accessors remain role-gated: student uses the logged-in student's id (`getStudentM*V2`),
  faculty use `getFacultyStudentM*V2(studentId)`; both honor 401/403/400 (covered by existing
  BFF tests). RBAC **PASS**.

## 8. Test / verification status
- `npx tsc --noEmit` → PASS (0 errors).
- `npm run test:frontend` → **161/161** pass (150 prior + 11 new `lib/v2-prediction-contract.test.ts`
  covering `m1V2GradeTone`, `m2V2SgpaTone`, `m3V2RiskTone`, `riskLevelLabel`, `formatRiskPercent`).
- ML V2 suite → 128 passed; full ML suite → 713 passed.
- Backend V2 tests (`test_m1v2/m2v2/m3v2_prediction.py`) → 94 passed.
- Supabase: **UNCHANGED** — no DDL/DML/migration schema changes this work.

## 9. Status codes
- **M1 V2 PRODUCTION READY:** PASS.
- **M2 V2 PRODUCTION READY:** PASS.
- **M3 V2 PRODUCTION READY:** FURTHER VALIDATION REQUIRED (28 positives, same-cohort holdout only).
- **UI:** PASS.
- **RBAC:** PASS.
- **REGRESSION:** PASS (frontend, ML, and V2 backend suites green; full backend suite has a
  pre-existing `test_analytics_service.py` ordering/event-loop flake that passes 46/46 when run
  alone and is unrelated to this work).
- **SUPABASE:** UNCHANGED.