# UI Strategy and Dashboard Experience

## 1. Purpose

This document defines how the product should feel and behave in the browser. It covers screen strategy, dashboard composition, role-specific presentation, and the UI rules that keep the product aligned with the backend-first architecture.

The UI is a consumer of verified backend outputs, not the place where academic or predictive logic should be invented.

## 2. Current UI Position

The current Next.js experience is intentionally minimal. The dashboards exist as placeholders that validate session flow, role routing, and page structure. That is the right foundation, but it is not the finished product.

## 3. UI Principles

- Design for role clarity first, not feature density.
- Keep the experience responsive and mobile-friendly.
- Favor readable, decision-oriented layouts over decorative dashboards.
- Show confidence, freshness, and provenance when data is derived or predictive.
- Avoid surfacing raw machine output without human context.

## 4. Role-Based Experience Model

### 4.1 Student Dashboard

The student view should emphasize personal progress, risk signals, attendance, subject performance, and grounded guidance. It should answer what the student should do next, not just what the numbers are.

### 4.2 Faculty Dashboard

The faculty view should emphasize cohort monitoring, flagged students, comparative views, and intervention context. It should help a faculty member move from signal to action quickly.

### 4.3 Admin Dashboard

The admin view should emphasize operational visibility, data completeness, and platform readiness. It should make the system legible from a governance perspective rather than from a student success perspective.

## 5. Dashboard Composition Rules

- Surface the most important summary first.
- Push detail into drill-down sections or secondary panels.
- Keep explanations adjacent to predictions or warnings.
- Show the last updated time for derived data.
- Separate live status from historical trends.

## 6. Interaction Model

The UI should support a progression from overview to detail:

1. Role landing page.
2. High-level summary cards.
3. Supporting trend or breakdown panels.
4. Drill-down into the underlying student, subject, or cohort context.

This progression works well for both desktop and mobile because it avoids forcing all detail onto the first screen.

## 7. Backend Dependency Rules

- UI routes should call backend APIs for business data.
- The UI should not calculate risk, attendance summaries, or guidance locally.
- Empty and loading states should be designed explicitly, because backend availability is part of the real user experience.
- The interface should remain useful even when some intelligence outputs are still unavailable.

## 8. Visual Direction

The implementation should stay consistent with the current Next.js stack and the project’s shadcn/ui and Tailwind foundation. Visual polish should support clarity, trust, and hierarchy rather than becoming the main story.

## 9. Completion Criteria

A dashboard module is only complete when:

- The backend data contract exists.
- The screen handles loading, empty, and error states.
- The role-specific content is grounded in real data.
- The layout works on small and large screens.
- The page is understandable without requiring source-code knowledge.
