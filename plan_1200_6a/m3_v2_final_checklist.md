# M3 V2 — Final Delivery Pass/Fail Checklist

**Model:** `m3_v2_at_risk` v2.0 — At-Risk Student Prediction (binary)
**Cohort:** CSE 6A — 1,200 students
**Scope:** ML artifact + backend API + frontend (student/faculty/admin) + tests + docs
**Status:** ✅ **READY** (all required checks PASS)

> This document is the final acceptance checklist for the M3 V2 deliverable, following the
> M1/M2 V2 discipline: audit → target → temporal/pipeline → leakage gate → class imbalance →
> validation → baselines → artifact → inference/explanation → backend/API → frontend → tests →
> regression safety → docs.

---

## Phase A — Data Audit

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| A1 | 1,200-student cohort loaded read-only | ✅ PASS | `m3_v2_data_audit.md` §2 (9,600 summary rows) |
| A2 | Grain `(student_id, semester_no)` unique | ✅ PASS | data audit §5, no duplicate grains |
| A3 | Label source columns validated | ✅ PASS | `semester_result` PASS/ATKT, backlog 0–2, no FAIL; ATKT ⟺ backlog>0 |
| A4 | Target reduces honestly to `backlog_count(T+1) > 0` | ✅ PASS | data audit §3, §4 |

## Phase B — Target Definition

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| B1 | Canonical at-risk rule locked | ✅ PASS | `config.TARGET_AT_RISK`, `m3_v2_data_audit.md` §4 |
| B2 | Valid observation T ∈ {1..6}, target T+1 ∈ {2..7} | ✅ PASS | `config.VALID_OBSERVATION_SEMESTERS`, `MAX_ACADEMIC_SEMESTER=7` |
| B3 | 200 positives / 165 distinct students verified | ✅ PASS | validation report §2 (rate 2.78%) |

## Phase C — Temporal / Pipeline

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| C1 | Label via within-student `shift(-1)` | ✅ PASS | data audit §5 |
| C2 | Training transitions T=1..5 / temporal holdout T=6 | ✅ PASS | validation report §6 (6,000 / 1,200 rows) |
| C3 | Preprocessor fit on train only | ✅ PASS | `preprocessing/pipeline.py`; feature contract §4 |

## Phase D — Leakage Gate (M3-specific)

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| D1 | No T+1 / future / placement feature in `X` | ✅ PASS | runtime `leakage_check`; `config.FORBIDDEN_FEATURES` |
| D2 | Current-T outcomes allowed as features | ✅ PASS | feature contract §3 (differs from M1/M2 lists) |
| D3 | Backend `check_no_leakage` returns `[]` | ✅ PASS | `test_m3v2_prediction.py` |
| D4 | `select_features` strips forbidden defensively | ✅ PASS | `test_m3v2_prediction.py::TestLeakageAtInference` |

## Phase E — Class Imbalance

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| E1 | `class_weight=balanced` only | ✅ PASS | `config.IMBALANCE_HANDLING` |
| E2 | No synthetic oversampling | ✅ PASS | config; validation report §2 |
| E3 | Threshold tuned on group-CV validation only | ✅ PASS | validation report §5; never holdout |

## Phase F — Validation

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| F1 | GroupKFold by student (15 folds, all informative) | ✅ PASS | validation report §4 |
| F2 | Temporal hold-forward T=6→7 | ✅ PASS | validation report §6 |
| F3 | Selection by CV F1 (evidence, not flagging) | ✅ PASS | random_forest F1 0.246, PR-AUC 0.219, ROC-AUC 0.917 |

## Phase G — Baselines

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| G1 | majority_class | ✅ BEATEN | holdout recall 0.571 vs 0.000; PR-AUC 0.282 vs 0.023 |
| G2 | prior_backlog_rule | ✅ BEATEN | holdout recall 0.571 vs 0.000 |
| G3 | ML beats baselines on held-out semester → READY | ✅ PASS | validation report §3, §7 |

## Phase I/J — Artifact & Inference

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| I1 | Artifact saved + reloaded | ✅ PASS | `m3_v2_at_risk.joblib`; `reload_test=PASS` |
| I2 | Prediction test passes | ✅ PASS | `prediction_test=PASS`; live predictor verified |
| J1 | READY path compute + signals verified | ✅ PASS | synthetic READY-path check; NO_DATA for semester-8 students |
| J2 | Signals honest (feature contributions, not causes) | ✅ PASS | response `note`; UI "Estimated risk" |

## Phase O/P — Backend / API

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| O1 | `GET /predict/m3v2/{student_id}` registered | ✅ PASS | `backend/app/api/v1/predict.py` |
| O2 | RBAC via `authorize_prediction_access` | ✅ PASS | 401/403 covered in `test_m3v2_prediction.py` |
| O3 | NO_DATA → 404; artifact missing → 503; other → 500 | ✅ PASS | route + service `_guard_readiness` |
| O4 | `algorithm` normalized to per-target dict (schema-safe) | ✅ PASS | real bug fixed in `inference/predictor.py` |
| P1 | Read-only (no Supabase writes) | ✅ PASS | no write paths in service/predictor |

## Phase R — Frontend

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| R1 | Shared TS contract `lib/m3v2-prediction.ts` | ✅ PASS | `M3V2PredictionData`, `m3V2RiskTone` |
| R2 | Student / Faculty / Admin typed clients | ✅ PASS | `getStudentM3V2`, `getFacultyStudentM3V2`, `getAdminStudentM3V2` |
| R3 | Student + Faculty cards wired into grids/pages | ✅ PASS | `m3v2-card.tsx`, `ml-insights-grid.tsx`, pages |
| R4 | Admin honest limitation notice | ✅ PASS | `academic-prediction-card.tsx` |
| R5 | "Estimated risk" framing (never certainty) | ✅ PASS | cards + schema note |

## Phase S — Tests

| # | Suite | Result |
|---|-------|--------|
| S1 | ML `test_m3_v2.py` | ✅ **43/43 pass** |
| S2 | Backend `test_m3v2_prediction.py` | ✅ **34/34 pass** |
| S3 | Frontend accessors (student/faculty/admin) | ✅ **13 new, 150/150 overall pass** |
| S4 | Typecheck `tsc --noEmit` | ✅ PASS |

## Phase T — Regression Safety

| # | Suite | Result |
|---|-------|--------|
| T1 | Full ML suite (M1 + M2 + M3 V2 + legacy) | ✅ **841/841 pass** |
| T2 | Backend suite (M1/M2/M3 V2 + rest) | ✅ **1442 pass** (excl. pre-existing analytics event-loop failures, which pass 87/87 in isolation and are unrelated to M3 V2) |
| T3 | Legacy M3 model/API untouched | ✅ PASS |
| T4 | M1 V2 / M2 V2 unchanged | ✅ PASS |
| T5 | Supabase read-only (no schema/data changes) | ✅ PASS |

## Phase U — Docs

| # | Document | Present |
|---|----------|---------|
| U1 | `m3_v2_data_audit.md` | ✅ |
| U2 | `m3_v2_feature_contract.md` | ✅ |
| U3 | `ml/v2/m3_at_risk_prediction/reports/m3_v2_validation_report.md` | ✅ |
| U4 | `m3_v2_production_readiness.md` | ✅ |
| U5 | This pass/fail checklist | ✅ |

---

## Overall Verdict

**M3 V2 is READY for production deployment as the at-risk estimator** (legacy M3 remains BLOCKED).
Every required pass/fail check is a PASS with evidence. The residue is entirely pre-existing and
unrelated to M3 V2 (legacy analytics event-loop tests, legacy lint warnings).

**Operational guardrails (carry forward):**
- Serve only a **next normal academic semester**; honor the NO_DATA boundary for the current
  semester-8 cohort.
- Present `probability_at_risk` and signals as **estimates / contributions**, never certainty or
  causation.
- Do not reuse M1/M2 forbidden lists for M3 (they would strip legitimate current-T outcomes).