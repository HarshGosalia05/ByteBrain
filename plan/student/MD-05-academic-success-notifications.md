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

# MD-05 — ACADEMIC SUCCESS INTELLIGENCE + NOTIFICATIONS

## 1. Objective

Convert verified marks, attendance, timetable, and academic trends into actionable student guidance and meaningful notifications.

Dependencies:
MD-02 + MD-03 + MD-04.

## 2. Academic Success

Plan:
- Academic Health Score
- Needs Attention
- What Should I Focus On?
- Top priorities
- strengths/weaknesses
- goal tracking
- SGPA target
- CGPA target
- semester/cohort trends
- credit-load vs performance

## 3. Rule-Based First

Clearly define deterministic rules before considering ML.

Examples:
- attendance threshold
- failing/weak subject
- declining trend
- backlog
- eligibility
- target gap

Do not call something ML unless predictive learning is actually required.

## 4. Academic Health Score

Design a transparent methodology.

Document:
- inputs
- normalization
- weights if any
- thresholds
- interpretation
- edge cases

Avoid arbitrary scoring.

## 5. Needs Attention

Plan priority ranking based on verified signals.

Example inputs:
- low attendance
- weak marks
- decline
- backlog
- approaching assessment
- goal gap

## 6. Notifications

Use existing:
`performance_change_log`
`attendance_change_log`
`student_messages`

First inspect current notification architecture.

Plan:
- new marks
- marks update
- attendance warning
- eligibility warning
- performance change
- timetable change
- unread count
- read/unread
- history

Avoid duplicate notification sources.

## 7. Notification Generation

Document:
event
→ rule
→ notification record
→ student API
→ UI

Prevent duplicate/spam notifications.

## 8. Realtime

Determine whether realtime is needed for:
- notification badge
- marks updates
- attendance updates

Recommend repository-compatible architecture.

## 9. Goal Tracking

Plan student-managed targets separately from authoritative academic data.

Students may set goals, but goals cannot alter grades/marks.

## 10. Acceptance Criteria

- Notifications are student-specific.
- New marks can generate notifications.
- Attendance warnings use verified thresholds.
- Duplicate notifications are prevented.
- Academic score is explainable.
- Student cannot modify authoritative academic values.
