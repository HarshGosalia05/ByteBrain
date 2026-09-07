# CAMPUSX ML MASTER ANALYSIS

**Audit date:** 2026-09-07 · **Author:** ByteBrain (ML dependency audit)
**Output location:** `plan/docs/ml_audit/`
**README & navigator** — this file consolidates all audit phases. See per-topic docs below.

---

## 1. What this audit covered (28-phase task)
- (a) Model inventory & classification (ML vs rule-based vs controlled reasoning)
- (b) Per-model end-to-end traces: **M1 (v1/v2/v3), M2, M3, M4, M5**
- (c) Feature contracts & verification against live data availability
- (d) UI pages, APIs, BFF, chatbot, admin/faculty tool dependencies
- (e) Artifacts, legacy/duplicates, data flow, security, tests
- (f) Forward-looking impact for the **NEW Clean M1_v3** (external package; NOT integrated)

**Constraint honored:** READ-ONLY audit — no source/model/DB changes; only documentation created under `plan/docs/ml_audit/`. Verified via `git status`/`git diff` (see §7).

---

## 2. Master findings

### 2.1 The model landscape at a glance
| Model | Kind | Target | Status | Production for 80 students? |
|---|---|---|---|---|
| M1 v1 (legacy) | ML · HistGBM | end_sem_marks | READY (legacy endpoint) | Synthetic-trained; metrics unreliable |
| **M1 V2** | ML · Ridge | end_sem_marks (39-feat) | READY (active UI) | **NO_DATA** (missing 14/25 features) |
| M1 V3 (synthetic) | ML · LinearRegression | end_sem_marks (8-feat) | Experimental | **PARTIAL** (attendance_percentage missing) |
| **NEW Clean M1_v3** | (external package) | TBD | **NOT IN REPO** | Depends on contract (see §5) |
| M2 V2 | ML · RF+Ridge | next-sem SGPA/% (34-feat) | READY | NO_DATA (att/learn aggregates empty) |
| M3 V2 | ML · RF | at-risk binary (35-feat) | READY | NO_DATA (same reason) |
| M3 v1 | ML | at-risk | **BLOCKED** | Never served |
| M4 | **Rule-based** | readiness score | READY | Deterministic; works where career data exists |
| M5 | Controlled mapping + GenAI | domain/gaps/roadmap | Active | Works on verified data |

### 2.2 Three most important facts for ANY future M1_v3
1. **The 80 production students (STU000xxx) lack 14/25 "rich" features** — `attendance_weekly`, `student_learning_activity`, `student_lifestyle_survey` are empty for them; `subject_domain` has no source. Only **9+2** features are reliably available (internal_M, mid_M, credits, semester, subject_type, is_male, prior_sgpa, prior_att, prior_n_sems + computable pre_endsem_pct, sgpa_drift).
2. **M1 V2's NO_DATA cohort-guard (`STU6A`) is the correct, honest behavior** — the plan (`plan_1200_6a/m1_production_model_audit_and_plan.md`) recommends keeping it and **NOT retraining** on the 80 students with incomplete features.
3. **A clean M1_v3 will only be broadly useful if its feature contract stays within the 9+2 available set.** Anything broader silently becomes all-NO_DATA.

### 2.3 Honesty/security posture (excellent baseline)
- Single RBAC gate for all `/predict` routes; faculty scope enforced server-side.
- M3 v1 forced BLOCKED at API level.
- NO_DATA instead of fabricated/imputed values.
- G0 verified-context boundary gates all LLM use; tools never touch SQL/sessions.
- M4 explicitly labeled rule-based; M5 never claims ML confidence.
- Append-only audit-store `ml_predictions`; additive `prediction_feedback`.

### 2.4 Tech-debt / risk register (short form)
| Item | Risk |
|---|---|
| M1 has 3 live implementations vying for one target | Confusion; ensure version naming |
| sklearn 1.8.0 artifacts read under 1.9.0 (version warnings) | Silent numeric drift risk |
| V2 artifacts need `ml/` on sys.path (verified failure without) | Deployment fragility |
| M2 V2 artifact 7.6 MB in-repo | Watch binary bloat |
| `test_m1v3_readonly.py` + V3 dataset point outside repo/C:\HET SHAH paths | Provenance/portability |
| Legacy `/predict/m1|m2|m3` endpoints remain | Intentional debt (read-only) |
| No artifact checksum/CI integrity check | LOW/CRITICAL (tamper) |

---

## 3. Page × API × Model cross-reference
| Surface | M1 | M2 | M3 | M4 | M5 | Backend |
|---|---|---|---|---|---|---|
| Student ML Insights page | V2/V3 cards + trend | V2 card + trend | V2 card | cards + insights bundle | career guidance card | `/predict/m1v2\|m1v3\|m2v2\|m3v2\|insights`, `/students/me/career/guidance` |
| Faculty ML insights | bundle | bundle | bundle | bundle | — | `/faculty/students/{id}/ml-insights` |
| Admin ML intelligence | aggregates | aggregates | aggregates | aggregates | — | `/admin/ml-intelligence` (+generate/status) |
| Student chat | m1 tool | m2 tool | m3 tool | m4 tool | career coach | `/chat` tools → persisted rows → G0 |
| Faculty/Admin chat | prediction-insights/aggregate tools | same | same | same | — | tool registry allowlist |

## 4. Dependency graph (core)
```
DB ──► feature layer (point-in-time, leakage-graded) ──► inference processors
        │                                                   │
        ▼                                                   ▼
   READ-ONLY GET /predict/*  (RBAC)   ◄── ML-08 explanations
        │
        ├─ /predict/insights/{id}  → page bundle
        └─ POST /predict/persist/{type}/{id} → ml_predictions (append-only)
                                              ├─ student page / chat tools / faculty / admin aggregates
                                              └─ prediction_feedback (additive)
```
(full detail: `ml_data_flow.md`, `m1_backend_dependency_map.md`, `chatbot_ml_dependency.md`)

## 5. NEW Clean M1_v3 — decision-ready summary
**Package status:** NOT in repo (search-verified). **Content required from user:** artifact + feature contract + package layout.
**Impact when integrated (max points of change):**
1. Backend: new endpoint + service (mirror V3 pattern; RBAC; NO_DATA; 503) + `resolve_model_version`.
2. Frontend: `lib/student-api.ts`/`lib/m1v3-prediction.ts`, page merge logic, `M1V3Card`.
3. Persistence key `m1` (append-only history; version-tagged) → chatbot/faculty/admin auto-read.
4. Tests: backend + lib + feature-overlap smoke test.
5. Decide grade-band policy + endpoint naming (clean vs synthetic V3).
**Gate:** feature-overlap vs the 9+2 available set; keep the honesty contract.
(full: `m1_replacement_impact.md`, `m1_feature_contract_current.md`)

## 6. Security & test posture (short form)
- Security: RBAC single-gate; tool allowlist fail-closed; 3 OK (own/authorized/institution scopes); G0 verified-context; honesty wording enforced in tests. → `ml_security_map.md`
- Tests: backend ML (M1V2/V3, M2V2, M3V2, contract, generation, insights, feedback, RBAC, M4) + ml package suite (v1 contract, M1 readiness/temporal/holdout, M2/M3 validation, insights APIs) + v2/v3 package tests + lib contract tests (auth gating, NO_DATA-200, 404/503, caching). Gaps: artifact checksums, mixed-version explanation test, card component tests, sklearn-pin smoke test. → `ml_test_coverage.md`

## 7. Change-control verification
- Only new markdown files authored under `plan/docs/ml_audit/`.
- `git status` / `git diff --stat` must show **zero** modifications to application/source/artifact/migration files (see terminal output bc task completion).

## 8. Document index (this folder)
| File | Content |
|---|---|
| `model_inventory.md` | Master inventory & ML-vs-rule-based classification |
| `m1_complete_trace.md` | Full M1 v1/V2/V3 trace (UI→API→service→artifact) |
| `m1_feature_contract_current.md` | Feature contracts + data availability |
| `m1_backend_dependency_map.md` | Backend dependency graph for M1 |
| `m2_trace.md` · `m3_trace.md` · `m4_trace.md` · `m5_trace.md` | Per-model traces |
| `ml_insights_page_map.md` | Student page → model map |
| `chatbot_ml_dependency.md` | Chatbot/tool → model map |
| `model_artifact_inventory.md` | 7 artifacts + sizes + pickled-class notes |
| `legacy_and_duplicate_models.md` | Overlap & cleanup status |
| `ml_data_flow.md` | DB→features→inference→persistence→surfaces |
| `page_model_matrix.md` · `api_model_matrix.md` · `model_data_source_matrix.md` | Cross matrices |
| `m1_replacement_impact.md` | NEW Clean M1_v3 impact analysis |
| `ml_security_map.md` · `ml_test_coverage.md` | Security & test maps |

---

*Prepared as a read-only analysis deliverable. No models, APIs, pages, chatbot behavior, database, or source code were modified.*