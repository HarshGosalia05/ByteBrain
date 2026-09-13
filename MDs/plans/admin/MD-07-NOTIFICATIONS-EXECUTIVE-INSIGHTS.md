TASK: Implement MD-07 — Admin Notifications/Announcements and Grounded Executive Insights.

PRECONDITION
MD-01 through MD-06 complete.

IMPORTANT
This is P2. If P0/P1 are incomplete, STOP and report that this MD should be deferred.

PART A — ADMIN ANNOUNCEMENTS

Reuse the EXISTING notification infrastructure.

Do NOT create a duplicate notification system/table.

Admin can create:
- Announcement
- Academic Notice
- Holiday
- Event
- System Notice

TARGET:
- Students
- Faculty
- Both

Required:
- title
- message
- type
- target audience
- created_at
- event_id only where appropriate

Respect existing notification lifecycle:
- unread
- read
- dismissed if already implemented

Use existing notification rules and repository patterns.

BACKEND:
Admin authorization required.

Do not allow Student/Faculty to create Admin announcements.

PART B — EXECUTIVE ACADEMIC SUMMARY

Only implement if deterministic analytics from previous MDs are complete.

Create an Admin "Executive Insights" section.

Input must be structured verified analytics:
- department performance
- attendance
- risk
- academic trend
- weak subjects
- career insights if available
- institution health

GenAI must NOT calculate raw statistics.

Architecture:

Verified Analytics
→ Structured Context
→ GenAI
→ Natural Language Summary

Example output:
- strongest department
- weakest academic area
- attendance concern
- risk concern
- notable trend
- recommended administrative focus

Every generated statement must be grounded in supplied structured values.

If GenAI integration is not already configured safely, do NOT fabricate it.
Instead create the deterministic executive-summary data structure and leave GenAI integration as a clearly documented extension.

TEST:
- admin announcement authorization
- recipient targeting
- notification creation
- deduplication where applicable
- executive insight context correctness
- no fabricated values

VERIFY:
backend tests
frontend tests
typecheck
lint
build