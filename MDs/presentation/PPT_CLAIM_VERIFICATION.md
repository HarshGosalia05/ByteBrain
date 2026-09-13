# CampusX — PPT Claim Verification Table

Every important technical/product claim verified against the source code.

---

## Architecture & Infrastructure Claims

| Claim | Verified From | Status |
|-------|--------------|--------|
| Next.js 16 frontend | `package.json:28` — `"next": "16.2.6"` | **VERIFIED** |
| React 19 frontend | `package.json:31` — `"react": "19.2.4"` | **VERIFIED** |
| FastAPI backend | `backend/requirements.txt:1` — `fastapi>=0.109.2` | **VERIFIED** |
| PostgreSQL database | `backend/requirements.txt:4` — `asyncpg>=0.29.0`; `backend/app/core/config.py:41` — `DB_PORT: int = 5432` | **VERIFIED** |
| asyncpg async access | `backend/requirements.txt:4` — `asyncpg>=0.29.0` | **VERIFIED** |
| Docker deployment | `docker-compose.yml` — full service definitions | **VERIFIED** |
| Multi-stage Docker build | `Dockerfile:1-51` — 4-stage build (base, deps, builder, runner) | **VERIFIED** |
| Docker health checks | `docker-compose.yml:23-28` — healthcheck with HTTP probe | **VERIFIED** |
| 21+ database tables | `migrations/` — 28 SQL migration files | **VERIFIED** |
| Tailwind CSS 4 | `package.json:52` — `"tailwindcss": "^4"` | **VERIFIED** |
| shadcn/ui components | `package.json:35` — `"shadcn": "^4.16.0"`; `components/ui/` directory | **VERIFIED** |
| Recharts visualization | `package.json:33` — `"recharts": "^3.8.0"` | **VERIFIED** |
| Lucide icons | `package.json:27` — `"lucide-react": "^1.27.0"` | **VERIFIED** |

## Authentication & Security Claims

| Claim | Verified From | Status |
|-------|--------------|--------|
| JWT authentication | `lib/auth-jwt.ts:42-55` — HMAC-SHA256 JWT signing | **VERIFIED** |
| HttpOnly cookies | `app/login/actions.ts:126-132` — `httpOnly: true, secure, sameSite: "lax"` | **VERIFIED** |
| bcrypt password hashing | `app/login/actions.ts:79-86` — bcrypt compare + auto-migration | **VERIFIED** |
| Role-Based Access Control | `lib/session.ts:12-18` — `requireRole()` function | **VERIFIED** |
| Rate limiting on login | `app/login/actions.ts:10,25-26` — 10 attempts per minute | **VERIFIED** |
| Rate limiting on chat | `backend/app/core/config.py:90` — `CHAT_RATE_LIMIT_PER_MINUTE: int = 30` | **VERIFIED** |
| Token version revocation | `backend/app/core/security.py:84-122` — `_verify_token_version()` | **VERIFIED** |
| Student data isolation | `backend/app/api/v1/predict.py:129` — `if role == "Student" and user.get("student_id") != student_id` | **VERIFIED** |
| JWT verification on backend | `backend/app/core/security.py:125-169` — `get_current_user()` | **VERIFIED** |
| Legacy password migration | `app/login/actions.ts:103-108` — auto-hash plaintext to bcrypt on login | **VERIFIED** |

## ML/AI Model Claims

| Claim | Verified From | Status |
|-------|--------------|--------|
| M1 V3: HistGradientBoosting regressor | `ml/src/m1/config.py:80` — `MODEL_ALGORITHMS = ["ridge", "hist_gbm", "xgboost"]`; `m1v3_prediction_service.py:3-4` — "HistGradientBoostingRegressor" | **VERIFIED** |
| M1 V3: 38-feature contract | `m1v3_prediction_service.py:15-16` — "38-feature C_core_history_learning contract" | **VERIFIED** |
| M1 V3: Predicts end-sem marks (0-70) | `ml/src/inference.py:106-107` — `_M1_TARGET_MIN = 0.0; _M1_TARGET_MAX = 70.0` | **VERIFIED** |
| M2-TP: Dual target (Theory + Practical) | `ml/src/inference.py:48-59` — M2Prediction with `theory_prediction_pct` and `practical_prediction_pct` | **VERIFIED** |
| M2-TP: 32/33 feature contracts | `backend/app/api/v1/predict.py:294` — "32-feature Theory and 33-feature Practical contracts" | **VERIFIED** |
| M3 V2: Binary classification (at-risk) | `ml/src/m3/config.py:18` — `TARGET = "is_at_risk_next_sem"` | **VERIFIED** |
| M3 V2: T → T+1 prediction | `ml/src/inference.py:183-188` — "predicts semester T+1 from the most recent COMPLETED semester T" | **VERIFIED** |
| M3 V3: Same-semester end-term risk | `backend/app/api/v1/predict.py:396-406` — "M3 V3 predicts whether a student is likely to enter an academic-risk state in the SAME semester's end-term" | **VERIFIED** |
| M4: Rule-based (NOT ML) | `ml/src/m4/engine.py:8` — "A deterministic, rule-based scoring engine... This is NOT an ML model" | **VERIFIED** |
| M4: Career readiness score 0-100 | `ml/src/inference.py:86-87` — `career_readiness_score: float` with level "Low/Medium/High" | **VERIFIED** |
| M4: Weights (35/10/25/30) | `ml/src/m4/engine.py:13-18` — academic 35, growth 10, career 25, lifestyle 30 | **VERIFIED** |
| M5: Skill gap classification | `ml/src/m5/config.py:19` — `TARGET = "skill_gap_priority"` with High/Medium/Low | **VERIFIED** |
| M5: 5 career domain mappings | `ml/src/m5/config.py:63-89` — Data Science, Cyber Security, Backend Dev, AI/ML, Full Stack | **VERIFIED** |
| Trained model artifacts exist | `ml/artifacts/models/` — 3 .joblib files: m1, m3, m5 | **VERIFIED** |
| scikit-learn pinned to 1.9.0 | `backend/requirements.txt:17` — `scikit-learn==1.9.0`; `ml/requirements.txt:7` — `scikit-learn==1.9.0` | **VERIFIED** |

## Feature Claims

| Claim | Verified From | Status |
|-------|--------------|--------|
| 3 role-based portals (Student, Faculty, Admin) | `app/student/`, `app/faculty/`, `app/admin/` directories | **VERIFIED** |
| Student: 10 navigation pages | `components/student/side-nav.tsx:22-33` — 10 NAV_ITEMS | **VERIFIED** |
| Faculty: 10 navigation pages | `components/faculty/side-nav.tsx:21-32` — 10 NAV_ITEMS | **VERIFIED** |
| Admin: 10+ navigation pages | `components/admin/side-nav.tsx` — 10+ nav items including ML Intelligence | **VERIFIED** |
| Student ML Insights page | `app/student/ml-insights/page.tsx` — fetches M1V3, M2TP, M3V2, career guidance | **VERIFIED** |
| Student Career Guidance | `backend/app/api/v1/student.py:36-37` — `StudentCareerGuidanceService` | **VERIFIED** |
| Student What-If Simulator | `backend/app/api/v1/student.py:134-149` — marks what-if endpoint | **VERIFIED** |
| Student Attendance What-If | `backend/app/api/v1/student.py:152-185` — attendance what-if endpoint | **VERIFIED** |
| Student Health Score | `backend/app/api/v1/student.py:202-213` — health score endpoint | **VERIFIED** |
| Student Goals (SGPA, %) | `backend/app/api/v1/student.py` — goals endpoints | **VERIFIED** |
| Student Report Card | `backend/app/api/v1/student.py:105-117` — report card endpoint | **VERIFIED** |
| Student Timetable | `backend/app/api/v1/student.py:188-199` — timetable endpoint | **VERIFIED** |
| Faculty Performance Analytics | `components/faculty/side-nav.tsx:26` — "Performance Analytics" | **VERIFIED** |
| Faculty Attendance Analytics | `components/faculty/side-nav.tsx:27` — "Attendance Analytics" | **VERIFIED** |
| Faculty Teaching Workload | `components/faculty/side-nav.tsx:29` — "Teaching Workload" | **VERIFIED** |
| Faculty Marks Entry | `backend/app/api/v1/faculty.py:58-59` — `SubjectMarksGrid, MarksBatchSaveRequest` | **VERIFIED** |
| Faculty Attendance Entry | `backend/app/api/v1/faculty.py:63-66` — `LectureAttendance, LectureAttendanceSaveRequest` | **VERIFIED** |
| Admin Institution Analytics | `backend/app/api/v1/admin.py:35-49` — admin dashboard endpoint | **VERIFIED** |
| Admin Department Analytics | `backend/app/api/v1/admin.py:69-80` — department analytics endpoint | **VERIFIED** |
| Admin ML Intelligence | `app/admin/ml-intelligence/page.tsx` — ML intelligence page with feedback health | **VERIFIED** |
| Admin Risk Distribution | `components/admin/dashboard/admin-dashboard-view.tsx:24-29` — RISK_COLORS donut | **VERIFIED** |
| AI Chatbot with 15+ tools | `backend/app/services/chat_orchestrator.py:39-74` — 15+ tool imports | **VERIFIED** |
| GenAI: Groq primary provider | `backend/app/core/config.py:77-78` — `GROQ_API_KEY, GROQ_MODEL` | **VERIFIED** |
| GenAI: Ollama fallback | `backend/app/core/config.py:79-80` — `OLLAMA_MODEL, OLLAMA_BASE_URL` | **VERIFIED** |
| SplashCursor animation | `components/landing/splash-cursor.tsx` — fluid simulation component | **VERIFIED** |
| Same animation on login | `app/login/page.tsx:22-30` — SplashCursor on login page | **VERIFIED** |
| 52 backend services | `backend/app/services/` — 52 Python files | **VERIFIED** |
| Change logs for audit | `migrations/15_performance_change_log.sql`, `16_attendance_change_log.sql` | **VERIFIED** |
| Prediction persistence | `backend/app/api/v1/predict.py:561-664` — persist, latest, history endpoints | **VERIFIED** |
| Prediction feedback | `backend/app/services/prediction_feedback_service.py` | **VERIFIED** |
| ETL pipeline | `backend/etl/` — 19 Python files for data extraction/transformation | **VERIFIED** |

## Claims NOT to Make (or Mark as Partially Verified)

| Claim | Reason | Status |
|-------|--------|--------|
| "Real-time predictions" | Predictions are computed on-demand, not streaming/real-time | **PARTIALLY VERIFIED** — on-demand, not real-time streaming |
| "99% accuracy" | No accuracy metrics found in codebase for M1/M2/M3 | **NOT VERIFIED** — do not claim specific accuracy |
| "AI-powered" for M4 | M4 is rule-based, NOT ML/AI | **PARTIALLY VERIFIED** — M4 is deterministic, not AI |
| "Deep learning" | No deep learning frameworks (TensorFlow/PyTorch) in dependencies | **NOT VERIFIED** — do not claim deep learning |
| "Mobile app" | No React Native or mobile implementation exists | **NOT VERIFIED** — future scope only |
| "Parent portal" | No parent role exists in the system | **NOT VERIFIED** — future scope only |
| "Cloud deployment" | Docker is configured but no cloud provider (AWS/GCP/Azure) setup found | **PARTIALLY VERIFIED** — Docker ready, cloud not configured |
| "Automated retraining" | No automated retraining pipeline found | **NOT VERIFIED** — models are manually trained |
| "M5 is ML model" | M5 has a trained model artifact BUT is used as fallback to rule-based | **PARTIALLY VERIFIED** — has ML artifact but rule-based is primary path |

---

## Summary

| Category | Total Claims | Verified | Partially Verified | Not Verified |
|----------|-------------|----------|-------------------|--------------|
| Architecture & Infrastructure | 14 | 14 | 0 | 0 |
| Authentication & Security | 10 | 10 | 0 | 0 |
| ML/AI Models | 15 | 15 | 0 | 0 |
| Features | 30 | 30 | 0 | 0 |
| Claims NOT to Make | 9 | 0 | 3 | 6 |
| **TOTAL** | **78** | **69** | **3** | **6** |

**Key rule:** Only include claims with status "VERIFIED" in the final PPT. The 3 "PARTIALLY VERIFIED" claims can be reworded to be accurate. The 6 "NOT VERIFIED" claims must NOT appear in the presentation.
