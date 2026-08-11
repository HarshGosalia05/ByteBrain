TASK: Implement MD-01 — KenexAI Admin Foundation.

OBJECTIVE
Create the production-ready Admin shell and Admin authorization foundation without implementing the actual analytics features yet.

SCOPE

1. Inspect the existing authentication/session architecture.
2. Identify the current Admin role representation.
3. Identify how Student and Faculty route protection is currently implemented.
4. Reuse the same authentication/session mechanism for Admin.
5. Add Admin-only route protection for /admin/*.
6. Enforce Admin authorization on backend endpoints that will be introduced later.
7. Create the Admin application shell.

ADMIN ROUTES
Create the minimum foundation for:

/admin
/admin/dashboard

If the existing project uses /admin as the dashboard route, preserve that convention rather than creating unnecessary duplicate routes.

ADMIN LAYOUT
Create:
- Admin shell/layout
- Sidebar
- Top bar
- Main content area
- Responsive behavior
- Mobile sidebar behavior if the existing application has this pattern

ADMIN SIDEBAR
Prepare navigation for the final Admin module:

Dashboard

Academic
  - Overview
  - Subjects
  - Departments

Attendance

Risk & Early Warning

Students

Faculty

Career Readiness

Lifestyle Insights

Notifications

Only Dashboard should be functionally active in this MD.
Future items may be disabled or linked only if the architecture already supports this cleanly.

ADMIN ACCESS CONTROL
Required:
- Admin can access /admin/*
- Student cannot access Admin
- Faculty cannot access Admin
- Unauthenticated users cannot access Admin

Authorization must exist on the backend/API layer too.

DO NOT:
- create Admin profile
- create Admin settings
- create CRUD
- create analytics
- create notifications
- create ML
- create GenAI

DASHBOARD PLACEHOLDER
Create a clean empty dashboard foundation that is ready for MD-02.
Do not add fake KPI cards.

UI REQUIREMENTS
- Existing KenexAI visual language
- Responsive
- Accessible
- Proper loading/error/empty states
- No global CSS redesign
- Reuse existing components where possible

TESTING
Add appropriate authorization tests:
- admin allowed
- student denied
- faculty denied
- unauthenticated denied

Verify:
npm run typecheck
npm run lint
npm run build
backend tests

STOP CONDITION
Do not implement MD-02 analytics in this task.