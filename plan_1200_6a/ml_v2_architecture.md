# ML v2 — Clean Isolated Architecture Proposal (M1, M2, M3, M4)

**Status:** PROPOSAL / DESIGN ONLY — no code written, no models created, nothing trained.
**Date:** 2026-08-31
**Companion doc:** `existing_ml_audit.md` (classifies every legacy component A–E).

This document defines a clean, isolated ML v2 stack. It must **not import or silently depend on any obsolete legacy model code** unless a dependency is explicitly approved below.

---

## 0. Design Principles (derived from the audit)

1. **No dependency on synthetic-data artifacts.** Every V1 headline metric (M1 MAE 3.18, M2 R² 0.997, M3 F1 0.80) is the output of a synthetic, near-stationary generator and must NOT be quoted as evidence. v2's first deliverable is a **real, non-synthetic, multi-cohort labeled dataset** and a *baseline gap* measurement against it.
2. **Leakage discipline is the deliverable, not accuracy.** GroupKFold-by-student, deployment-row exclusion, forbidden-feature blocklists, T+1 temporal correctness, and the statistical validation gate are carried forward intact. A model is only "good" if its validation is provably leak-free, not because SA/ROC are high.
3. **Statistical gate before productization.** A model is only promotable when it passes a pre-declared minimum-informative-sample gate (e.g., N positive students ≥ k×folds). M3 must not ship until real positives exist.
4. **Isolation.** v2 lives in its own namespace (`mlv2/`) and owns its own data pipeline, features, artifacts, and validation. It may reuse only the **explicitly approved** service-layer interfaces from V1 (registry/persistence/explainability contracts), never the trained model code or artifacts.
5. **Data-driven contracts, not hardcoded.** Replace the hardcoded 2-department / fixed-column assumptions with contract discovery from the data layer.
6. **Reproducibility & test coverage.** All steps are versioned (features, data, config, artifact) and gated by pytest; throwaway `verify_*.py` scripts are replaced by real test suites.

---

## 1. Target Architecture (topology)

```
mlv2/
├── pyproject.toml / requirements.txt        # v2-only pinned deps (+ asyncpg explicit)
├── config/
│   ├── settings.py                          # paths, seeds, fold counts, gating thresholds
│   ├── contracts.py                         # data-driven feature contracts (no hardcode)
│   └── leakage_policy.py                    # forbidden-feature registries (curated)
├── data/                                    # v2 owns its own data layer
│   ├── loaders.py                           # read-only loaders (DB-backed via backend repo or CSV)
│   ├── resolver.py                          # row → (features, target, deployment_flag) @ grain
│   └── provenance.py                        # dataset versioning, cohort metadata, hashes
├── features/
│   ├── builders.py                          # per-model feature builders
│   ├── contracts.py                         # raw + encoded feature contracts
│   └── validators.py                        # null/range/categorical/grain checks
├── labeling/
│   ├── academic.py                          # canonical T+1 outcome label (single source of truth)
│   └── audit.py                             # conflict/ambiguity/duplicate detection
├── validation/                              # THE core of v2
│   ├── splits.py                            # GroupKFold-by-student + temporal hold-forward
│   ├── isolation.py                         # student isolation, deployment exclusion checks
│   ├── leakage.py                           # forbidden-column & T+1 integrity checks
│   ├── gates.py                             # statistical sufficiency gate (promotion gate)
│   └── metrics.py                           # leak-free metric computation + reporting
├── models/
│   ├── m1/                                  # subject end-marks regression
│   ├── m2/                                  # next-semester performance regression
│   ├── m3/                                  # at-risk classification
│   └── m4/                                  # career readiness (rule engine, versioned)
├── serving/
│   ├── registry.py                          # v2 model registry (typed load)
│   ├── inference.py                         # v2 predict wrappers
│   ├── persistence.py                       # json-safe row mapping (reuse V1 contract)
│   └── explain.py                           # grounded explanations (reuse V1 contract)
├── api/                                     # optional FastAPI integration layer (later)
├── tests/                                   # pytest for every module above
└── artifacts/                               # v2 artifacts (versioned, hash-pinned)
    └── models/  +  reports/  +  datasets/
```

**Isolation boundary / explicit approvals (the critical rule):**
- v2 **MAY reuse** (as interfaces/contracts, not trained models):
  - `ml/src/registry.py` loader pattern & ModelType enum (*approved*)
  - `ml/src/prediction_persistence.py` json-safe mapping (*approved*)
  - `ml/src/explain.py` explanation result contract (*approved*)
- v2 **MUST NOT import** (obsolete/synthetic/unsafe):
  - Any `ml/src/m1`, `ml/src/m2`, `ml/src/m3`, `ml/src/m4` *training/eval/artifact* code
  - `ml/src/features.py` / `feature_config.py` / `feature_data.py` hardcoded contracts (replace with data-driven)
  - `ml/src/retrain_m3.py` (leakage/label divergences) — *blocked unless rewritten*
  - `ml/src/m4/*train*`, `ml/src/m4_backup/` legacy supervised-ML
- If any legacy module is later needed, it must be **explicitly approved** before import; silent reuse is prohibited.

---

## 2. Data Strategy (prerequisite — do FIRST)

The single most important v2 activity. All model rebuilds depend on it.

### 2.1 Requirements for a valid v2 training dataset
- **Real (non-synthetic) outcomes** — actual exam results, attendance, and per-semester summaries with genuine variability (not a stationary generator).
- **≥2 admission cohorts** with a genuine chronological relationship, so temporal hold-forward is meaningful (V1 has a single 2023 cohort → cannot do this).
- **Grain alignment:** subject-level (M1), semester-level (M2/M3), student-level (M4).
- **Label sources:** canonical academic label builder for M3 (single source of truth); **never** `prediction_feedback` as ground truth (audit: feedback is a review label, not truth).
- **Explicit deployment boundary** per cohort (last observable semester per student).

### 2.2 Data provenance
- Each dataset snapshot gets: source cohort, academic year range, schema hash, row counts per grain, generation timestamp, and a lineage note.
- Feature/target dictionaries are versioned so metric comparisons are apples-to-apples.

### 2.3 Contract discovery
- Replace hardcoded `department_name_BBA/CSE` and fixed columns with a discovered categorical domain (any number of departments/departments encoding), validated at build time.

---

## 3. Model-by-Model v2 Plan

### M1 — Subject End-Marks (regression)
- **Goal:** predict `end_sem_marks` [0,70] during semester T (post internal/mid/attendance).
- **Approved reuse:** GroupKFold-by-student, temporal multi-holdout machinery (port the *logic*; do not import V1 module).
- **v2 changes:**
  1. Train on real multi-cohort data; use genuinely future cohorts as the holdout.
  2. Feature-selection controlled; forbid the same-semester-family columns only where they are not available at the true prediction point.
  3. Reference a **naive baseline** (predict prior-semester mean / linear decay) so skill is measured as lift-over-baseline, not absolute MAE.
  4. Report **temporal-window MAE per cohort** in addition to CV MAE.
- **Promotion gate:** MAE must beat the naive baseline on a *future cohort never seen in any fit*; else don't promote.

### M2 — Next-Semester Performance (regression)
- **Goal:** predict `next_semester_percentage` / `next_semester_sgpa` from current semester.
- **Approved reuse:** GroupKFold-by-student + deployment exclusion (port logic).
- **v2 changes:**
  1. **Treat near-1.0 R² as a red flag.** Add an explicit "autocorrelation sanity check": if the model's R² approaches the naive "carry-forward previous value" R², flag it as uninformative.
  2. Require genuine temporal holdout (future cohort) — the current single-cohort CV cannot prove forward skill.
  3. Compare against a "predict previous semester value" baseline.
- **Promotion gate:** beats carry-forward baseline on a held-out future cohort.

### M3 — At-Risk (binary classification)
- **Goal:** predict whether next semester is FAIL/ATKT or backlog>0.
- **Approved reuse:** the **statistical validation gate** (`v1_m3_validation_gate.py` logic — port, do not import), canonical **label builder** (`v1_label_builder.py` logic), and GroupKFold. These are the most valuable parts of the V1 stack.
- **v2 changes:**
  1. Obtain sufficient real positive students (target ≥ 2×n_folds ≈ 10 unique positives) before any promotion. **Until then M3 is BLOCKED by design.**
  2. Use **only** the canonical label rule. Remove the `sgpa<4.0` and `department_code` divergences from the retraining path; unify schema.
  3. Use **GroupKFold by student everywhere** — no StratifiedKFold path. Fix/eliminate `retrain_m3.py`.
  4. Report precision/recall/F1/PR-AUC on informative folds only, and explicitly report folds that had no positives (never fabricate).
- **Promotion gate:** gate verdict PASS **and** ≥ N informative folds **and** > M unique positive students **and** metrics stable across folds. Otherwise remain BLOCKED.

### M4 — Career Readiness (rule engine)
- **Goal:** transparent, explainable career-readiness score.
- **Approved reuse:** the rule engine logic (port `engine.py` / `m4_career_readiness.py` into `mlv2/models/m4/`), with declared weight provenance.
- **v2 changes:**
  1. Move weights into a versioned config so the score's provenance is auditable.
  2. Do **not** drop rows on missing lifestyle/academic fields silently — impute explicitly or mark them "insufficient history" (keep V1's neutral-slope handling for trend).
  3. **Do not** create/recreate the contradictory `build_m4.py` joblib claim; keep M4 as `RULE_BASED`, versioned in the registry with weights hash.
  4. Optionally expose a "confidence"/"coverage" flag (data-complete vs. estimated).
- **Recommendation:** **KEEP** (no ML rebuild needed). Legacy supervised-ML M4 is archived (obsolete/duplicate).

---

## 4. Validation Gate — MANDATORY for all v2 promotions

Every model must pass a pre-registered leak-free validation before any production exposure:

1. **Leakage checks (must pass):** no target in features; T+1 strictly future; deployment rows excluded; no train/val student overlap; preprocessing fit on train only; forbidden-feature list enforced.
2. **Statistical sufficiency gate (must pass):** unique positive/rare-class sample ≥ configured threshold; informative folds ≥ threshold; no degenerate class in any fold (or explicitly reported).
3. **Temporal generalization (must pass for any forward claim):** metric on a future cohort never seen in fit; report lift over a declared baseline.
4. **Metric trust node:** each reported metric carries: fold count, unique subject/student count, whether computed on informative folds only, and the baseline it beats.

**Consequence:** any model failing the gate is registered as `BLOCKED` and returns no production prediction (mirroring V1's correct M3 behavior).

---

## 5. v2 Service Layer (isolated)

- **Registry** (`mlv2/serving/registry.py`): typed `ModelEntry` + `ModelType(JOBLIB|RULE_BASED)`, safe `joblib.load`, shape validation, deterministic-prediction check, artifact hash tracking. *(Pattern approved from V1 `registry.py`.)*
- **Inference** (`mlv2/serving/inference.py`): per-model predict wrappers that always route through feature contracts + validators.
- **Persistence** (`mlv2/serving/persistence.py`): `json_safe` row mapping — reuse V1 contract shape for frontend compatibility.
- **Explainability** (`mlv2/serving/explain.py`): grounded, rule-based explanations; never hallucinate confidence/importance.
- **Feedback** (`mlv2/serving/feedback.py`): faculty review labels stored separately from ground truth; validated against `actual_at_risk` before being considered for retraining.

---

## 6. Guardrails (v2)

- **Never** deprecate/overwrite a V1 artifact while V1 is still referenced by the running service; promote v2 behind a registry version switch or a separate serving route.
- **Never** train on synthetic data and report it as real performance.
- **Never** promote M3 without the statistical gate.
- **Never** use `prediction_feedback` as ground-truth labels for training.
- **All** v2 datasets, features, and artifacts versioned + hash-pinned; every metric traceable.

---

## 7. Suggested Incremental Roadmap (post-audit; NOT executed now)

1. **Phase 0 — Data readiness.** Stand up a real, multi-cohort, non-synthetic dataset with provenance + contract discovery. Gate: dataset is leak-free, grain-aligned, cohort-chronological.
2. **Phase 1 — Naive baselines.** Compute carry-forward / prior-mean baselines and the "autocorrelation sanity check" so every future model is compared to a real reference.
3. **Phase 2 — M4 port** (rule engine) into `mlv2/models/m4/` with versioned weights. Low risk; do first for quick win.
4. **Phase 3 — M1 rebuild** on real data with temporal multi-holdout + baseline lift.
5. **Phase 4 — M2 rebuild** on real data with carry-forward baseline gate.
6. **Phase 5 — M3** only after sufficient real positive class; gate-blessed promotion.
7. **Phase 6 — Serving integration** behind registry version switch; retire V1 artifacts only after v2 passes gates and is shadow-validated against the real service.

STOP — audit complete. No code, models, or migrations created beyond these two documents.
