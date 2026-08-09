# KENEXAI — STUDENT MODULE
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

# MD-04 — STUDENT DAILY ASSISTANT

## 1. Objective

Turn existing timetable and academic context into a useful daily student experience without changing authoritative academic data.

## 2. Scope

Plan:
- today's classes
- next class
- weekly timetable
- subject details
- free slots
- study suggestions
- weak-subject priorities
- upcoming classes
- assignments/deadlines
- submission tracking
- exam reminders
- daily priorities

## 3. Repository Audit

Inspect:
- timetable APIs
- timetable components
- subject APIs
- assignment tables
- examination tables
- submission tables
- notification tables
- existing calendar/deadline components

Do not invent a table if an existing one supports the feature.

## 4. Timetable Stitching

Verify:

student department
+
semester
+
academic year
+
weekly_timetable_07

Map timetable subject IDs to enrolled subjects.

Document:
- day/time handling
- current timezone
- duplicate timetable rows
- cancelled/missing class behavior

## 5. Free Slot Logic

Use deterministic scheduling logic.

Plan:
- today's occupied slots
- free slots
- optional study recommendation inputs

Do not use GenAI to calculate free time.

## 6. Study Priorities

Use verified academic/attendance signals from MD-02/MD-03.

Potential inputs:
- weak subject
- attendance shortage
- upcoming exam
- deadline
- target gap

Clearly distinguish rules from future ML/GenAI.

## 7. Deadline Sources

Inspect actual repository tables first.

If assignments/exams/submissions are not implemented, explicitly mark the feature as:
"Dependency not verified / defer."

Do not fabricate schema.

## 8. API Plan

Document existing and required endpoints.

## 9. UI Plan

Reuse existing dashboard/timetable patterns.

## 10. Acceptance Criteria

- Today's classes are based on canonical timetable.
- Next class is calculated correctly.
- Free slots are deterministic.
- No fake deadlines appear.
- Study priorities use verified data.
- Existing timetable functionality remains intact.
