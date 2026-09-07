# Legacy & Duplicate Models

Identifies overlapping/legacy artifacts and code paths that serve the same logical prediction so replacement planning (esp. for the NEW Clean M1_v3) accounts for every duplicate.

## M1 — three live implementations of the same target
| Path | Role | Data provenance | Quality honesty |
|---|---|---|---|
| `/predict/m1` → v1 artifact `m1_subject_endmarks` | Legacy "production" contract endpoint | **Synthetic** 80-student data | Untrustworthy metrics (correlations 0.86–0.99) — `plan_1200_6a` explicitly calls M1 V1 metrics unreliable |
| `/predict/m1v2` → `m1_v2_subject_endmarks` | **Production** (active UI) | Real 1,200 CSE 6A | Honest CV MAE 6.319 / R² 0.434; cohort-guarded `STU6A` |
| `/predict/m1v3` → `m1_v3_clean` (`ml/M1_v3_CampusX_package`) | Production; clean V3 replaces the synthetic V3 (removed 2026-09-07) | Real CampusX data, 38-feature `C_core_history_learning` | Test MAE≈6.29 / R²≈0.44 on a temporal holdout; not comparable to M1V2 (different feature contract) |

**M1 = explicitly 3 models.** Any "replace M1 with new Clean M1_v3" must decide which endpoint(s) it displaces: legacy `/predict/m1`, `/predict/m1v2`, `/predict/m1v3`, or all three.

## M2 — two implementations
- v1 `m2_next_semester_performance` (dict of 2 Pipelines) → `/predict/m2` legacy; active UI is V2-only (`plan_1200_6a/ml_legacy_cleanup_report.md`: LEGACY CLEANUP PASS).
- V2 `m2_v2_next_semester` → `/predict/m2v2` production.

## M3 — two implementations, one deliberately disabled
- v1 `m3_next_semester_at_risk` → `/predict/m3` **BLOCKED** by unified contract + route-level rejection (403 on non-BLOCKED).
- V2 `m3_v2_at_risk` → `/predict/m3v2` production.

## M4 — no duplicates (single deterministic engine)
`ml/src/m4/engine.py`; also referenced by `ml/src/registry.py ModelEntry(model_type=RULE_BASED)`. Admin and student surfaces both consume persisted `m4` rows (single source of truth: `ml_predictions`).

## M5 — no duplicates by design
`student_career_coach_tool` replaces four separate career placeholders (`plan` docs: G2.2→G2.5); `student_career_rules` is the single approved taxonomy.

## Residual cleanup status
- `plan_1200_6a/ml_legacy_cleanup_report.md` → Phase 1 complete: active UI is V2-only for M1/M2/M3, obsolete files zero-referenced.
- Legacy `/predict/m1|/m2|/m3` endpoints remain routed (read-only) — removal is intentional-debt, not required for correctness.
- `test_m1v3_readonly.py` (repo root, stale machine paths) and `plan_1200_6a/dry_run_m1v3.py` were removed with the synthetic V3 on 2026-09-07.

## Decision matrix for NEW Clean M1_v3 integration
| Question | Current state to resolve |
|---|---|
| Does the clean model replace the synthetic V3 (`/predict/m1v3`)? | Decide: keep V3 endpoint experimental or remove it |
| Does it shadow M1V2 (`/predict/m1v2`)? | Decide: only if it is trained on real data with honest validation gates |
| Legacy `/predict/m1`? | Likely leave untouched (read-only, not in UI) |
| Persistence key | All persist under `prediction_type='m1'`; new rows would mix model versions in one history — acceptable per append-only ML-06 design, but `model_version` must be tagged so `PredictionInsightsService`/explanations don't mix |