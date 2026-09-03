# CAMPUSX — STUDENT MODULE
# PLANNING ONLY — DO NOT IMPLEMENT ANYTHING

## Global Rules

- Inspect the real repository before proposing implementation changes.
- Do not invent filenames, endpoints, tables, columns, hooks, services, or relationships.
- If something cannot be verified, state: "Not verified in repository."
- Reuse → Extend → Create New.
- Do not rebuild working Student or Faculty functionality.
- Do not modify `global.css`.
- Do not create duplicate academic tables.
- Do not seed, overwrite, delete, or modify real academic data.
- Student academic data is strictly READ-ONLY.
- Faculty/Admin are responsible for authoritative academic writes.
- Business logic and authorization belong in FastAPI/backend.
- Next.js remains UI/BFF/screen-shaping layer.
- PostgreSQL/Supabase remains the canonical source of truth.
- Never treat NULL academic values as zero.
- Every plan must include security, performance, loading/empty/error states, testing, regression checks, and exact verified files.

# MD-01 — STUDENT INTELLIGENCE FOUNDATION

## 1. Objective

Establish the verified Student 360 foundation that all later Student Module MDs can safely reuse.

This MD must audit and plan the existing implementation rather than rebuild it.

## 2. Scope

Analyze:

- Existing Student Dashboard
- Academic page
- Subjects page
- Attendance page
- Profile
- Notifications foundation
- Settings foundation
- Existing Student APIs
- Existing FastAPI services/repositories
- Authentication and authorization
- Existing Faculty Marks implementation
- Existing Faculty Attendance implementation
- Existing database relationships
- Current semester context
- Student ownership/read-only enforcement
- Loading/empty/error behavior

Do not implement MD-02 through MD-08 features.

## 3. Repository Audit

Identify exact verified paths for:

### Frontend
- Student routes
- layouts
- pages
- components
- hooks
- API clients/BFF handlers
- charts
- tables
- cards
- auth providers
- loading/error states

### Backend
- FastAPI entry point
- routers
- services
- repositories
- Pydantic schemas
- auth middleware
- role checks
- database client
- Student APIs
- Faculty Marks APIs
- Faculty Attendance APIs

### Database
Inspect actual schema/migrations/queries for:
- students
- student_subject_enrollment
- student_subject_performance
- attendance
- daily_attendance_07
- student_semester_summary
- weekly_timetable_07
- subjects
- faculty
- career_preferences
- lifestyle_survey
- faculty_student_map
- risk_predictions
- performance_change_log
- attendance_change_log
- student_messages

## 4. Student 360 Data Contract

Plan a backend-owned aggregation containing, where verified:

- identity
- enrollment
- current semester
- enrolled subjects
- current marks/performance
- current attendance
- semester history
- timetable context
- career context
- future intelligence placeholders

Determine which data is:
- independently fetched
- joined
- aggregated
- derived
- canonical
- future-phase data

Do not create a duplicate warehouse/table solely for the Student UI unless the repository proves it is required.

## 5. Canonical Join Map

Explicitly verify:

students.student_id
→ student_subject_enrollment.student_id

student_subject_enrollment.enrollment_record_id
→ student_subject_performance.enrollment_record_id

student_subject_enrollment.enrollment_record_id
→ attendance.enrollment_record_id

students.student_id
→ daily_attendance_07.student_id

students.student_id
→ student_semester_summary.student_id

students.student_id
→ career_preferences.student_id

students.student_id
→ lifestyle_survey.student_id

For each join document:
- key
- cardinality
- duplicate risk
- NULL behavior
- repeat-attempt implications
- performance implications

## 6. Faculty → Student Live Data

Plan the verified flow:

### Marks
Faculty UI
→ existing write endpoint/service
→ student_subject_performance
→ performance_change_log where applicable
→ Student read API
→ Student UI

### Attendance
Faculty UI
→ existing attendance endpoint/service
→ daily_attendance_07
→ attendance aggregation
→ attendance_change_log where applicable
→ Student read API
→ Student UI

Do not duplicate Faculty calculation or persistence logic.

## 7. Read-Only Security

Audit:
- student role identification
- authenticated student_id
- ownership checks
- query-parameter spoofing
- backend authorization
- database/RLS controls
- direct browser-to-database access
- cache isolation

Plan fixes only; do not implement them in this planning task.

## 8. Live Update Strategy

Compare:
- API refetch/revalidation
- polling
- Supabase Realtime
- hybrid

Recommend the safest repository-compatible approach.

## 9. API Inventory

Create:

| Endpoint | Method | Purpose | Tables | Consumer | Reuse/Extend/New |
|---|---|---|---|---|---|

Identify the minimum APIs genuinely required for the Student 360 foundation.

## 10. Frontend Mapping

Create:

| Page | Existing Component | Existing Hook/API | Reuse | Change |
|---|---|---|---|---|

Preserve existing UI and design system.

## 11. States

Plan:
- student not found
- unauthorized
- no current semester
- no subjects
- no marks
- partial marks
- no attendance
- API failure
- authentication expiry
- stale data

Never show fake academic data.

## 12. Future Dependencies

Map how MD-01 supports:

MD-02 → marks intelligence
MD-03 → attendance intelligence
MD-04 → daily assistant
MD-05 → success + notifications
MD-06 → career + support
MD-07 → privacy/accessibility
MD-08 → ML + GenAI

## 13. Acceptance Criteria

- Student sees only their own records.
- Academic records remain read-only.
- Faculty Marks data is reused.
- Faculty Attendance data is reused.
- No duplicate academic tables.
- Existing Student UI remains compatible.
- global.css remains untouched.
- APIs are repository-grounded.
- Missing data is handled explicitly.

## 14. Required Final Output

Return:
1. Executive summary
2. Repository audit
3. Database mapping
4. Join map
5. Student 360 contract
6. API inventory
7. Frontend mapping
8. Security findings
9. Live-data recommendation
10. Performance findings
11. Exact files to reuse/change
12. Exact files not to touch
13. Implementation order
14. Acceptance criteria

DO NOT IMPLEMENT.
