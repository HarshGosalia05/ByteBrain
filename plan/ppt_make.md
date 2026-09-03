# PPT_SOURCE_CONTENT.md — Fact-Gathering Task List

> **Purpose**: This checklist maps each required section of `PPT_SOURCE_CONTENT.md` to the specific files, folders, and data sources that will be inspected for verified facts.  
> **Rule**: READ-ONLY — no code modifications, no DB writes, no installs.

---

## Section 1 — Team & Project Identity

| # | Inspection Target | What to Extract |
|---|---|---|
| 1.1 | `plan/status/00_kenexai_project_master_status.md` §1 | Project name, one-line description, KDAC-3 problem statement (verbatim) |
| 1.2 | `plan/00_project_scope_and_principles.md` §2 | Cross-check problem statement wording |
| 1.3 | `plan/reference/KDAC3_KenexAI_Master_Blueprint.md` | Original KDAC-3 brief if quoted |

---

## Section 2 — Solution Summary

| # | Inspection Target | What to Extract |
|---|---|---|
| 2.1 | `plan/status/00_kenexai_project_master_status.md` §1, §14, §15 | What is actually built today vs what is planned |
| 2.2 | `plan/00_project_scope_and_principles.md` §1 | Mission / value proposition |

---

## Section 3 — Data Stitching / Student 360

| # | Inspection Target | What to Extract |
|---|---|---|
| 3.1 | `plan/data_engineering/02_data_stitching_and_identity_resolution.md` | Stitching key design, identity resolution approach |
| 3.2 | `backend/etl/stages/stitch.py` | Actual stitching key used in code (`student_id`, composite key, etc.) |
| 3.3 | `backend/etl/stages/extract.py` | Source tables extracted |
| 3.4 | `supabase_export_all_dataset_backup/*.csv` | Verify which data domains have actual rows (academic, attendance, career, lifestyle) |
| 3.5 | `plan/03_database_schema_and_etl_pipeline.md` | Designed stitching vs implemented |

---

## Section 4 — System Architecture

| # | Inspection Target | What to Extract |
|---|---|---|
| 4.1 | `plan/02_system_architecture_and_service_boundaries.md` | Designed architecture layers, service boundaries |
| 4.2 | `plan/status/00_kenexai_project_master_status.md` §3 | Project architecture section |
| 4.3 | `package.json` | Next.js version, frontend deps |
| 4.4 | `backend/requirements.txt` | FastAPI version, backend deps |
| 4.5 | `backend/app/main.py` | FastAPI app entry point, CORS, routers |
| 4.6 | `backend/Dockerfile` | Docker status |

---

## Section 5 — Data Warehouse Design

| # | Inspection Target | What to Extract |
|---|---|---|
| 5.1 | `plan/data_warehouse.md` | Layer model (staging/canonical/gold), designed schema |
| 5.2 | `plan/status/00_kenexai_project_master_status.md` §6 | Database overview — live tables, categories |
| 5.3 | `backend/db_schema_inspect.json` | Actual DB schema introspection output |
| 5.4 | `migrations/*.sql` | All 22 migration files — verify table creation order |
| 5.5 | `supabase_export_all_dataset_backup/*.csv` | Row counts per table (line count each CSV) |

---

## Section 6 — ETL Pipeline

| # | Inspection Target | What to Extract |
|---|---|---|
| 6.1 | `plan/data_engineering/01_reusable_etl_architecture.md` | 7-stage pipeline model design |
| 6.2 | `backend/etl/stages/` — all `.py` files | Verify each stage: extract, validate, transform, stitch, derive, load + stage.py base |
| 6.3 | `backend/etl/cli.py` | CLI runner, orchestration |
| 6.4 | `backend/etl/runner.py` | Pipeline runner logic |
| 6.5 | `backend/etl/validation.py` | Data quality validation |
| 6.6 | `backend/etl/config.py` | Pipeline configuration |

---

## Section 7 — Role-Based Dashboards

| # | Inspection Target | What to Extract |
|---|---|---|
| 7.1 | **Student routes** — `app/student/*`: `dashboard/`, `academic/`, `attendance/`, `ml-insights/`, `notifications/`, `profile/`, `report-card/`, `settings/`, `subjects/`, `timetable/` | List each page, check `page.tsx` for real data vs placeholder |
| 7.2 | **Faculty routes** — `app/faculty/*`: `dashboard/`, `attendance/`, `notifications/`, `performance/`, `profile/`, `settings/`, `students/`, `subjects/`, `timetable/`, `workload/` | Same — real data vs placeholder |
| 7.3 | **Admin routes** — `app/admin/*`: `dashboard/`, `academic/`, `analytics/`, `attendance/`, `career/`, `faculty/`, `health/`, `ml-intelligence/`, `notifications/`, `risk/`, `students/` | Same — real data vs placeholder |
| 7.4 | `plan/status/00_kenexai_project_master_status.md` §8, §11 | Faculty module status, frontend architecture |
| 7.5 | `plan/05_ui_strategy_and_dashboard_experience.md` | Designed vs implemented UI |

---

## Section 8 — ML Models

| # | Inspection Target | What to Extract |
|---|---|---|
| 8.1 | `ml/artifacts/models/` | Actual .joblib files: `m1_subject_endmarks.joblib`, `m2_next_semester_performance.joblib`, `m3_next_semester_at_risk.joblib` |
| 8.2 | `ml/src/m1/`, `ml/src/m2/`, `ml/src/m3/`, `ml/src/m4/` | Training source code for each model |
| 8.3 | `ml/m4_career_readiness.py`, `ml/m4_report.md` | M4 career readiness model status |
| 8.4 | `ml/src/explain.py` | SHAP / explainability implementation |
| 8.5 | `ml/src/prediction_service.py` | Prediction serving logic |
| 8.6 | `ml/src/prediction_persistence.py` | Where predictions are stored (table name) |
| 8.7 | `supabase_export_all_dataset_backup/ml_predictions.csv` | Actual row count of predictions generated |
| 8.8 | `supabase_export_all_dataset_backup/risk_predictions.csv` | Row count of risk predictions |
| 8.9 | `plan/04_analytics_ml_and_genai_engine.md` | Designed ML pipeline vs implemented |

---

## Section 9 — GenAI

| # | Inspection Target | What to Extract |
|---|---|---|
| 9.1 | `plan/04_analytics_ml_and_genai_engine.md` | GenAI architecture design |
| 9.2 | `backend/app/api/v1/chat.py` | Chat endpoint — actual implementation vs stub |
| 9.3 | `lib/chat-api.ts` | Frontend chat API client |
| 9.4 | `plan/status/00_kenexai_project_master_status.md` §13 | Analytics architecture (includes GenAI status) |
| 9.5 | `grep` for `genai`, `gemini`, `openai`, `llm`, `grounding` across `backend/` | Verify if any LLM integration is actually coded |

---

## Section 10 — Tech Stack

| # | Inspection Target | What to Extract |
|---|---|---|
| 10.1 | `package.json` | Frontend dependencies + versions |
| 10.2 | `backend/requirements.txt` | Backend dependencies + versions |
| 10.3 | `ml/requirements.txt` | ML dependencies |
| 10.4 | `plan/status/00_kenexai_project_master_status.md` §4 | Complete tech stack section |
| 10.5 | `backend/Dockerfile` | Docker status |
| 10.6 | Look for `docker-compose.yml` / `docker-compose.yaml` at repo root | Docker Compose presence |
| 10.7 | `tsconfig.json` | TypeScript config |

---

## Section 11 — Known Gaps / Risks

| # | Inspection Target | What to Extract |
|---|---|---|
| 11.1 | `plan/status/00_kenexai_project_master_status.md` §21 | Risks / Technical Debt section — pull verbatim |
| 11.2 | `plan/06_delivery_roadmap_quality_and_operations.md` | Delivery risks, quality gaps |
| 11.3 | `plan/status/00_kenexai_project_master_status.md` §15, §16 | Features in progress, future modules |

---

## Section 12 — Current Statistics

| # | Inspection Target | What to Extract |
|---|---|---|
| 12.1 | `plan/status/00_kenexai_project_master_status.md` §19 | Current Project Statistics section |
| 12.2 | `backend/app/api/v1/*.py` | Count actual API endpoints defined |
| 12.3 | `app/student/*/page.tsx`, `app/faculty/*/page.tsx`, `app/admin/*/page.tsx` | Count actual frontend routes |
| 12.4 | `supabase_export_all_dataset_backup/*.csv` | Cross-check row counts per table |
| 12.5 | `backend/db_schema_inspect.json` | Cross-check table count from schema introspection |

---

## Execution Order

```
1.  Read master status doc fully (§1–§22)              → Sections 1,2,4,5,7,8,9,10,11,12
2.  Read plan/00 through plan/06                       → Sections 1,2,3,4,5,6,9,11
3.  Read plan/data_engineering/01, 02, 03              → Sections 3,5,6
4.  Read plan/data_warehouse.md                        → Section 5
5.  Inspect backend/etl/stages/*.py                    → Section 6
6.  Inspect backend/app/api/v1/*.py                    → Sections 4,12
7.  Inspect app/student/*/page.tsx                     → Section 7
8.  Inspect app/faculty/*/page.tsx                     → Section 7
9.  Inspect app/admin/*/page.tsx                       → Section 7
10. Inspect ml/artifacts/models/                       → Section 8
11. Inspect ml/src/ key files                          → Sections 8,9
12. Grep for GenAI keywords across backend/            → Section 9
13. Read package.json, requirements.txt, Dockerfile    → Section 10
14. Count rows in supabase_export CSVs                 → Sections 5,8,12
15. Read db_schema_inspect.json (table list)           → Sections 5,12
16. Compile contradictions and gaps                    → Section 11
17. Write PPT_SOURCE_CONTENT.md                        → Final output
```

---

> **Status**: Awaiting user confirmation before proceeding with fact-gathering.
