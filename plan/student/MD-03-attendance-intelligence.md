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

# MD-03 — ATTENDANCE INTELLIGENCE

## 1. Objective

Extend the existing Student Module to consume live Faculty attendance and provide accurate attendance intelligence.

Primary sources:
`daily_attendance_07`
`attendance`
`weekly_timetable_07`

Supporting:
`student_subject_enrollment`, `students`.

## 2. Scope

Plan:
- overall attendance
- subject-wise attendance
- daily attendance
- history/calendar
- present/absent/total
- percentage
- eligibility
- shortage
- attendance risk
- required classes
- safe absences
- recovery plan
- exam eligibility
- trend
- forecast candidate

## 3. Faculty Attendance Audit

Inspect exact:
- frontend
- endpoint
- service
- repository
- daily write
- aggregate update
- status values
- date handling
- lecture/slot handling
- change log
- update behavior

Student must consume the same records.

## 4. Data Stitching

Verify:

student_id
+
subject_id
+
semester_no
+
academic_year

and, where applicable:

enrollment_record_id

Document duplicate and repeat-attempt risks.

## 5. Deterministic Attendance Intelligence

Plan exact server-side formulas for:
- percentage
- eligibility
- shortage
- required classes
- maximum safe absences
- recovery

Do not use GenAI for arithmetic.

## 6. Daily Attendance

Plan:
- calendar/history
- present/absent status
- subject filter
- semester filter
- empty states
- correction/change visibility where appropriate

## 7. Forecasting

Determine whether historical data is sufficient for:
- statistical forecast
- ML forecast
- no forecast

Do not force ML if data is insufficient.

## 8. Realtime

Compare:
- refetch
- polling
- Supabase Realtime
- hybrid

Recommend one based on existing implementation.

## 9. API Plan

Inventory and classify all attendance endpoints.

## 10. UI Plan

Reuse existing Attendance page and dashboard cards/trends.

## 11. Acceptance Criteria

- Faculty attendance updates appear in Student view.
- Subject attendance is accurate.
- Daily history matches canonical data.
- Eligibility is deterministic and consistent.
- Required-class calculations are correct.
- Student cannot modify attendance.
- No duplicate attendance table or write path is introduced.
