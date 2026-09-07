# ML Insights Page Map (Frontend)

**Route:** `/student/ml-insights` (Student role only; `requireRole("Student")`).
**Page:** `app/student/ml-insights/page.tsx`

## Data loading (server-side, `dynamic="force-dynamic"`)
Two sections run in parallel:

**SemesterTrendSection** → `Promise.allSettled` of:
- `getStudentM1V2()` → `/predict/m1v2/{id}`
- `getStudentM1V3()` → `/predict/m1v3/{id}`
- `getStudentM2V2()` → `/predict/m2v2/{id}`
- `getStudentSemesterHistory(studentId)` → `/analytics/students/{id}/semester-history`

**MlInsightsSection** → `Promise.allSettled` of:
- `getStudentMlInsights()` → `/predict/insights/{id}` (bundle: M1–M4 + ML-08 explanations)
- `getStudentCareerGuidance()` → `/students/me/career/guidance` (M5)
- `getStudentM1V2()`, `getStudentM1V3()`, `getStudentM2V2()`, `getStudentM3V2()`

## Component tree
```
MlInsightsPage (app/student/ml-insights/page.tsx)
├─ PageHeader
├─ SemesterTrendSection
│   └─ SemesterTrendChart  (components/student/ml-insights/semester-trend-chart.tsx)
│        inputs: history semesters, predictedNextSemester (from M2V2 READY),
│                currentSemester predicted marks (M1V3 preferred, else M1V2)
└─ MlInsightsSection
    └─ MlInsightsGrid  (components/student/ml-insights/ml-insights-grid.tsx)
        ├─ M3V2Card          (components/student/ml-insights/m3v2-card.tsx)      — M3 V2
        ├─ M2V2Card          (…)m2v2-card.tsx                                    — M2 V2
        ├─ M1V3Card          (…)m1v3-card.tsx        (rendered when m1v3 exists)
        │   (or V2NoDataNote when m1v3 NO_DATA)
        ├─ M1V2Card          (…)m1v2-card.tsx        (only when no M1V3 data)
        │   (or V2NoDataNote when m1v2 NO_DATA)
        ├─ M4InsightsCard    (…)m4-insights-card.tsx — models.m4 from insights bundle
        └─ M4CareerGuidanceCard (…)m4-career-guidance-card.tsx — guidance (M5)
```

## NO_DATA handling
- M1V2/M1V3 return 200 with `readiness_status=NO_DATA` + optional `reason` → page extracts `m1v2Reason`/`m1v3Reason` and renders `V2NoDataNote`.
- M2V2/M3V2 NO_DATA → backend 404 → page surfaces `error.message` as reason.

## Shared wrapper
`components/student/ml-insights/model-card.tsx` (`ModelCard`) — the common card shell (title, model badge, description, disclaimer, footer) reused by the four model cards.

## API clients (lib/)
- `lib/student-api.ts` — `getStudentMlInsights` (:631), `getStudentM1V2` (:642), `getStudentM1V3` (:653), `getStudentM2V2` (:666), `getStudentM3V2` (:680), `getStudentCareerGuidance` (:755, 30s timeout).
- `lib/m1v2-prediction.ts`, `lib/m1v3-prediction.ts`, `lib/m2v2-prediction.ts`, `lib/m3v2-prediction.ts` — typed response models.
- `lib/analytics-api.ts` — `getStudentSemesterHistory`.
- All prediction reads flow through BFF `callApiV1` with `BFF_TTL_MS` caching; career guidance uses `callFastapi("career/guidance", …)` directly. BFF layer routes: `app/api/…` passthroughs (fastapi fetch) — only `app/api/admin/ml-intelligence/generate/*` and `app/api/chat/route.ts` are ML-related BFF handlers; all other ML reads call FastAPI directly from server components.

## Other ML-touching pages (for the page×model matrix)
- Faculty: `app/faculty/…/ml-insights`-ish pages → `GET /faculty/students/{student_id}/ml-insights` (`faculty.py:310`, scoped via `assert_student_in_scope`) → `PredictionInsightsService.get_student_insights`.
- Admin: `app/admin/…/ml-intelligence` → `GET /admin/ml-intelligence` + `POST /admin/ml-intelligence/generate` + status polling (`admin.py:286,309,355`) via `AdminMLService` / `AdminMLGenerationService`.
- Admin/Early Warning: `app/admin/…` flagged-student views (deterministic risk, NOT M3).

## Migration impact notes (for NEW Clean M1_v3)
- M1V3 promotion today means `M1V3Card` wins over `M1V2Card`; a clean M1_v3 would reuse `M1V3Card` (or a new variant) + `lib/m1v3-prediction.ts` type evolution and the two `SemesterTrendSection`/`MlInsightsSection` call sites in `page.tsx`.
- The page requires the `NO_DATA` contract; a clean model that returns marks without the readiness envelope would break rendering.