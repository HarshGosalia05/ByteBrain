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

# MD-06 — CAREER INTELLIGENCE + STUDENT SUPPORT

## 1. Objective

Provide deterministic career alignment and safe student-support workflows using existing academic and career data.

Dependencies:
MD-01 through MD-05 where relevant.

## 2. Career Intelligence

Plan:
- career profile
- readiness score
- target-role alignment
- career gaps
- skills
- internships
- certifications
- placement readiness
- elective advisor
- higher-study guidance

## 3. Career Data

Inspect:
`career_preferences`
`students`
`student_subject_performance`
`student_subject_enrollment`
`student_semester_summary`

Also discover:
- skills
- certificates
- internships
- placement tables

Do not invent tables.

## 4. Career Matching

Initially use deterministic/configuration-based matching.

Document:
- target role
- required skills
- academic evidence
- gaps
- readiness
- recommendation rules

GenAI may later explain results but should not be the authoritative matching engine.

## 5. Student Support

Plan:
- faculty doubt box
- subject questions
- responses
- history
- attendance dispute
- marks recheck
- grievance
- backlog roadmap
- repeat-attempt support
- achievement vault
- digital ID
- QR ID

## 6. Academic Dispute Safety

Student requests must create workflow/request records.

They must NOT directly update:
- marks
- attendance
- grades
- SGPA
- CGPA

Faculty/Admin must review and perform authoritative changes.

## 7. Privacy

Career and support data should be student-scoped.

Sensitive information must not be exposed to unauthorized Faculty/Admin users.

## 8. Acceptance Criteria

- Career alignment is explainable.
- Student can view and manage allowed profile/preferences.
- Academic records remain read-only.
- Disputes do not directly modify canonical data.
- Faculty responses are properly scoped.
- No duplicate academic source is introduced.
