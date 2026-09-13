# 07 — Student Module Planning

**Owns:** Student role experience end-to-end. **Depends on:** plan files 02 (architecture), 03 (schema), 05 (UI strategy), 06 (roadmap). **Scope rule:** build only against the existing, verified FastAPI Student APIs; no new backend architecture; no auth changes; no DB/migration changes.

---

## 1. Student Module Goals

1. Give each student a single, accurate, up-to-date view of their academic standing (profile, semester history, subject performance, attendance) using only the three existing FastAPI endpoints.
2. Replace the `/student/dashboard` placeholder with a real, data-driven overview while the full module is delivered in vertical slices.
3. Follow the backend-first → BFF → UI discipline: every screen consumes a shaped BFF response backed by a verified FastAPI contract; no business logic computed in the UI.
4. Deliver a mobile-first, role-scoped, accessible (WCAG 2.1 AA) experience consistent with the locked tweakcn/Twitter design system in `globals.css`.
5. Reserve Notifications, Settings, AI/ML and GenAI surfaces as explicit placeholders with designed empty states — never fabricated data.

**Out of scope:** edits to the `users` table or auth flow; writes of any kind; CGPA or risk computation in the frontend; any new backend service boundary.

---

## 2. Complete Page Hierarchy

Routes under the existing `app/student/` group (protected by `requireRole("Student")`):

| Route | Page | Data source |
|---|---|---|
| `/student/dashboard` | Overview | Profile + Academic Summary + Performance (BFF-aggregated) |
| `/student/academic` | Academic history | Academic Summary |
| `/student/academic?semester=N` | Semester detail (filtered view) | Academic Summary (client filter via `use-search-params`) |
| `/student/subjects` | Subject performance | Performance |
| `/student/attendance` | Attendance view | Academic Summary + Performance |
| `/student/profile` | Profile (read-only) | Profile |
| `/student/notifications` | Notifications | **Placeholder** (no API) |
| `/student/settings` | Settings | **Placeholder** (read-only) |

No dynamic route segments required in this phase (semester filtering is a client-side/URL-param concern on single pages). A shared `app/student/layout.tsx` renders the module shell (sidebar + header) once; pages render only their content region.

---

## 3. Sidebar Navigation

Twitter-style left rail, sticky, full height on desktop; slide-over drawer on mobile (off-canvas).

Items (lucide icons, locked tokens only):
- Dashboard — `LayoutDashboard`
- Academic — `GraduationCap`
- Subjects — `BookOpen`
- Attendance — `CalendarCheck`
- Profile — `User`
- Notifications — `Bell` (badge disabled in this phase; reserved)
- Settings — `Settings`

Behavior: active item highlighted with `--primary` treatment; active detection via `use-pathname`; items are `Link`s; component `components/student/side-nav.tsx`. Drawer on mobile uses a client `Sheet`-style component added from shadcn registry.

---

## 4. Header/Navbar

Sticky top header across the module (`components/student/top-bar.tsx`):
- Left: menu/chevron button (mobile) to open the drawer + page title.
- Right: theme toggle (existing `next-themes` pattern), student avatar (initials from first/last name — no image asset yet), overflow menu with **Sign out** (client action clearing the `session` cookie via a thin server action; do not redesign auth, only consume it).
- Header remains visible and consistent across all student pages; content scrolls beneath it.

---

## 5. Dashboard Sections (Overview)

Server component fetches all three APIs through the BFF; renders in this order:

1. **Welcome / identity strip** — first name, department, enrollment no, current semester (from Profile).
2. **Stat cards row** — Latest SGPA, Latest attendance %, Active backlogs, Credits earned. Values are the *latest-semester row* from Academic Summary (screen shaping only — no CGPA math).
3. **SGPA trend panel** — line/area chart across semesters (Academic Summary).
4. **Attendance trend panel** — line chart across semesters (Academic Summary).
5. **Current-semester subjects panel** — compact list/table of Performance rows where `semester === current_semester` (filter is shaping), linking to `/student/subjects`.
6. **Quick links** to Academic / Subjects / Attendance (tiles).

Freshness label ("Updated …") from BFF response metadata.

---

## 6. Academic Pages

`/student/academic` — semester history:
- **Summary table** (semantic `<table>` via shadcn `table` + `@tanstack/react-table`): Semester, SGPA, credits earned, attendance %, backlogs. Only fields present in the API.
- **SGPA + Attendance dual-axis chart** across semesters.
- **Backlog highlight** — row/badge emphasis when `active_backlogs > 0` (presentation only).
- Semester selector (tabs or `select`) reflecting the current semester; URL param `?semester=N` for shareable/deep-linkable state.
- Empty copy when summaries is empty.

No page needs a separate dynamic route in this phase; the single page with URL-param filter covers it.

---

## 7. Attendance Pages

`/student/attendance`:
- **Semester attendance trend** (Academic Summary attendance_percentage per semester).
- **Subject-wise attendance table** for the selected semester (Performance rows: subject, attendance %), with status badge (Eligible/Shortage-style presentation mapped from thresholds **only as a label, not a business rule** — plain color/icon + text per plan file 05 §10.1).
- Threshold interpretation is avoided in the UI; the raw percentage is displayed. Any "shortage" labeling stays purely cosmetic (e.g. low-value styling) and is clearly non-authoritative.
- Empty state when no attendance data exists.

---

## 8. Subject Pages

`/student/subjects`:
- **Subject performance table** (`@tanstack/react-table`): Semester, Subject code, Subject name, Internal, External, Total, Grade, Attendance %. Sortable and filterable by semester.
- **Semester filter** (tabs or select) synced to `?semester=`.
- **Per-semester bar chart** of Total marks by subject (recharts, `--chart-*` tokens).
- Grade badges colored via chart tokens with text/icon so color is never the only cue.
- Loading skeletons, empty state, error state with retry.

---

## 9. Profile Pages

`/student/profile` — read-only, from Profile API:
- Identity card (avatar initials, full name, student id, department, enrollment no).
- Details list (admission year, current semester) using `Field`/`Label` styling for read-only rows.
- A clear "Settings for editing are coming later" empty-state hint in Settings, not here.
- No edit capability (no PATCH endpoint exists).

---

## 10. Notifications

Placeholder page with a designed empty state: "No notifications yet" + short explanation that AI/ML-driven alerts and faculty/mentor messages will appear here in a future phase. Route exists, sidebar item exists, header title exists. No API call. Reserved badge slot in the sidebar.

---

## 11. Settings

Placeholder page: read-only "coming soon" with a list of future capabilities (theme is already available via existing provider; nothing else). No writes. Optionally show the student's profile summary read-only as a courtesy (reuses Profile API) but keeps edits explicitly out of scope.

---

## 12. Component Hierarchy

```
app/student/
  layout.tsx            → SideNav + TopBar + <main>{children}</main> (server; requireRole)
  dashboard/page.tsx    → DashboardView (server fetch → client chart panels)
  academic/page.tsx     → AcademicView
  subjects/page.tsx     → SubjectsView
  attendance/page.tsx   → AttendanceView
  profile/page.tsx      → ProfileView
  notifications/page.tsx, settings/page.tsx → placeholder views

components/student/
  side-nav.tsx, top-bar.tsx, dashboard/, academic/, subjects/, attendance/, profile/
components/shared/
  state/, layout/, data/
components/ui/          (shadcn primitives — registry only)
```

Server components own data fetching; client components are leaf interactives (charts, sortable tables, tabs, drawer, theme).

---

## 13. Reusable Components

Shared (`components/shared/`):
- `page-header.tsx` — title + description + freshness.
- `stat-card.tsx` — token-styled stat with icon, label, value.
- `chart-card.tsx` — panel wrapper (Card) for recharts.
- `data-table.tsx` — typed wrapper around `@tanstack/react-table` + shadcn `table` (sort/filter/paginate, semantic markup).
- `state/loading-skeleton.tsx`, `state/empty-state.tsx`, `state/error-state.tsx` (with retry), `state/section-suspense.tsx`.
- `freshness-badge.tsx` — "Updated …" indicator.
- `avatar-initials.tsx`, `grade-badge.tsx`, `trend-chart.tsx` (recharts line/area wrapper), `bar-chart.tsx`.

Domain (`components/student/`): `side-nav.tsx`, `top-bar.tsx`, `semester-select.tsx`, plus one view component per page section. All use `cn()`, tokens from `globals.css`, and `data-slot` conventions (plan file 05 §12).

Add from shadcn registry (CLI, not hand-written): `table`, `badge`, `skeleton`, `avatar`, `tabs`, `select`, `sheet`, `dropdown-menu`, `tooltip`, `separator` (exists), `sonner` (exists as dep). Recharts and `@tanstack/react-table` are already installed.

---

## 14. State Management

- **No global state library.** Server components + `next/navigation` `use-search-params`/`use-router` for filter state; React local state for UI (tabs, table sort, drawer).
- **Data access layer:** `lib/student-api.ts` — typed client used only inside BFF route handlers (server-side), with typed response interfaces aligned to the FastAPI OpenAPI shapes.
- **Cache:** short-TTL at the BFF for the three endpoints per plan file 05 §13 (use Next 16 caching primitives — `cacheLife`/`unstable_cache` — with a configurable TTL; verify exact API in `node_modules/next/dist/docs/01-app/03-api-reference` before implementation per AGENTS.md).
- **Staleness:** BFF returns a `fetchedAt`/freshness field; UI renders `freshness-badge`. No revalidation loop in this phase.

---

## 15. API Mapping (existing FastAPI APIs)

| Page / Section | BFF route (thin) | FastAPI endpoint | Payload used |
|---|---|---|---|
| Global (all pages) | `app/api/student/profile/route.ts` | `GET /api/v1/students/me/profile` | identity fields |
| Dashboard stats + trends + recent subjects | `app/api/student/dashboard/route.ts` (aggregates) | `/me/profile`, `/me/academic-summary`, `/me/performance` | latest row, per-semester arrays, current-semester rows |
| Academic | `app/api/student/academic-summary/route.ts` | `GET /me/academic-summary` | summaries |
| Subjects | `app/api/student/performance/route.ts` | `GET /me/performance` | performance |
| Attendance | `app/api/student/attendance/route.ts` (aggregates) | `/me/academic-summary` + `/me/performance` | semester + subject attendance |
| Profile | reuse profile BFF | `GET /me/profile` | — |
| Notifications / Settings | none | none | placeholder |

**BFF contract pattern (plan file 05 §13.3/13.4):** read `session` cookie → forward as `Authorization: Bearer <base64(session JSON)>` to FastAPI (reuses the temporary auth bridge) → translate FastAPI errors into structured UI errors → shape response + `fetchedAt` → short-TTL cache. **BFF never computes CGPA/risk/trend math.**

---

## 16. Additional APIs Required

Only one configuration addition, zero new backend endpoints:

1. **FastAPI base URL** for the BFF (non-secret). Add a single env var (e.g. `FASTAPI_URL`, defaulting to `http://localhost:8000`) — flagged as a one-line change to `.env.local`/config, confirmed acceptable since it is non-secret configuration. This is the *only* allowed touch to env.
2. **Session dependency note:** the current bridge returns `400` when the session JSON lacks `student_id` (corrupt seed data in `05_users_data.sql`). The BFF must treat that as a scoped error state ("account not fully linked") rather than a crash. No backend change — flagged as a data-quality dependency to resolve separately from this module.
3. Notifications/Settings write APIs are **explicitly deferred** (placeholder screens), per the "only if absolutely necessary" rule.

---

## 17. Mobile-First Responsive Strategy

- Layout from a 320px base upward (plan file 05 §10.4): single-column content, off-canvas nav on mobile → fixed left sidebar ≥ `lg`.
- Stat cards: 2-across on mobile, 4-across on desktop.
- Tables: horizontal scroll with a pinned first column on small screens, or card-list alternative at < `sm` (plan file 05 §14.7).
- Touch targets ≥ 44px; no hover-only interactions; `recharts` sized responsively (no horizontal page scroll).
- Test every slice at 320/375/768/1280 per the checklist.

---

## 18. tweakcn/Twitter UI Implementation Strategy

- Everything renders from `globals.css` tokens only: `--background`, `--card`, `--border`, `--radius`, `--chart-1..5`, `--sidebar-*`, shadows. **No hardcoded hex/oklch/spacing in components.**
- Twitter-style language: thin borders, tight radius, subtle hover via `hover:bg-muted`, sticky left rail + top bar, emphasis on whitespace and typographic hierarchy.
- Components added via `npx shadcn@latest add …` (base-nova style per `components.json`); customize only through `className` props and `cn()`.
- Dark mode parity required on every component (tested both palettes).
- New tokens, if truly needed, go into `globals.css` and are documented — not scattered in components.

---

## 19. Loading, Empty, Error and Skeleton States

- **Route-level:** `app/student/loading.tsx` (skeleton shell) and `error.tsx` (retry + friendly message) per plan file 05 §14.2–14.4.
- **Widget-level:** `Suspense` + per-section skeletons sized to the layout (no layout shift).
- **Empty:** explicit message per section ("No semester summaries yet", "No notifications yet") — visually distinct from loading.
- **Error:** translated BFF errors (never raw status/stack); inline retry; partial failure shows available sections with a stale/partial banner rather than a full page failure (plan file 05 §13.4).
- **Data freshness:** `freshness-badge` on every derived/predicted section; warning treatment when older than the refresh TTL.

---

## 20. Charts & Tables

- **Charts:** recharts only; tokens `--chart-1..5`; line/area for SGPA & attendance trends, bar for subject totals; axis labels + legend + a text summary (accessible alternative) required (plan file 05 §14.6).
- **Tables:** `@tanstack/react-table` + shadcn `table`; semantic `thead/tbody/th` with `scope`; sortable columns; pagination when rows exceed ~10; mobile-friendly overflow strategy.
- No arbitrary colors anywhere.

---

## 21. Folder/Component Structure

```
app/student/
  layout.tsx  loading.tsx  error.tsx
  dashboard/page.tsx
  academic/page.tsx
  subjects/page.tsx
  attendance/page.tsx
  profile/page.tsx
  notifications/page.tsx
  settings/page.tsx
app/api/student/            (BFF route handlers)
  profile/route.ts  academic-summary/route.ts  performance/route.ts  dashboard/route.ts  attendance/route.ts
components/student/
  side-nav.tsx  top-bar.tsx  semester-select.tsx
  dashboard/  academic/  subjects/  attendance/  profile/  placeholders/
components/shared/
  state/  data/  layout/  charts/
components/ui/              (shadcn primitives only)
lib/student-api.ts          (typed BFF client helpers)
```

---

## 22. Development Order (small vertical slices)

Each slice ends with `typecheck`, `lint`, `build`, and a manual state check (plan file 06 §4 Definition of Done).

1. **Foundation:** student `layout.tsx` (role gate preserved), `side-nav`, `top-bar`, shared state components, BFF plumbing (`lib/student-api.ts` + one health-check fetch), `loading.tsx`/`error.tsx`, FastAPI URL config. All section pages exist as empty scaffolds.
2. **Slice A — Dashboard:** identity strip, stat cards, SGPA trend, attendance trend, current-semester subjects.
3. **Slice B — Academic:** summary table + semester filter + charts.
4. **Slice C — Subjects:** performance table, sorting/filtering, bar chart.
5. **Slice D — Attendance:** semester trend + subject table.
6. **Slice E — Profile:** read-only identity/details.
7. **Slice F — Placeholders:** notifications, settings, plus AI/ML & GenAI reserved panels on the dashboard (see §24).
8. **Hardening pass:** mobile audit, dark-mode audit, accessibility pass, freshness badges, final build.

---

## 23. Testing Checklist

- `npm run typecheck`, `npm run lint`, `npm run build` all clean on every slice.
- Role scoping: a non-student session cannot reach `/student/*` (existing `requireRole` preserved); a Student cannot reach `/faculty/*` or `/admin/*`.
- Login as a valid Student → correct redirect → all module pages render real data (or correct empty/error states).
- BFF: correct forwarding of the session token; FastAPI 400/401/403/503 mapped to designed UI states; stale/cached responses carry freshness.
- States: loading skeletons, empty (no data), error+retry, partial failure each verified.
- Responsive: 320/375/768/1280; no horizontal scroll; 44px touch targets; drawer/sidebar toggle.
- Dark/light parity on every section.
- Accessibility spot-check: keyboard nav, `role="alert"`/`aria-live` on errors, chart text alternatives, semantic tables.

---

## 24. Future Placeholders for AI/ML & GenAI (do not implement)

Reserve clearly-labeled, non-functional panels so the architecture stays visible without faking data:
- **Dashboard "AI Insight" panel** — empty state: "Grounded AI summaries arrive with the GenAI insight layer (plan 04)". No LLM calls, no fake narratives.
- **Notifications** — reserved for at-risk alerts, faculty/mentor messages, and insight delivery (driven by `Risk_Predictions`/`GenAI_Insights` in a later phase).
- **Career guidance / readiness** — placeholder tile linking nowhere yet; the FastAPI career engine is not built.
- These placeholders must never render hardcoded insights or predictions.

---

### Pre-flight requirements before implementation
1. Add the single non-secret `FASTAPI_URL` config value (only env/config change allowed).
2. Confirm FastAPI is runnable locally (`uvicorn app.main:app` from `backend/` or the existing Dockerfile) so the BFF has a live target.
3. Note the `05_users_data.sql` linkage issue as a blocking data-quality dependency for full student logins (resolved outside this module).
