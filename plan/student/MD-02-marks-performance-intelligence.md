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

# MD-02 — MARKS & PERFORMANCE INTELLIGENCE

## 1. Objective

Extend the existing Student Module to consume and intelligently present the live marks already entered by Faculty.

Primary source:
`student_subject_performance`

Supporting sources:
`student_subject_enrollment`, `student_semester_summary`, `students`, `subjects`.

## 2. Scope

Plan:

- Internal marks
- CT1
- CT2
- Mid-semester
- End-semester
- Total
- Percentage
- Grade
- Grade point
- Result status
- Subject performance
- Semester performance
- SGPA/CGPA
- Performance trends
- Strengths/weaknesses
- Component-level weak-area detection
- Learning gaps
- Privacy-safe class-average comparison
- Backlogs
- Attempt history
- Marks simulator
- Academic What-If
- Target marks calculator

## 3. Faculty Data Reuse Audit

Inspect the exact Faculty Marks implementation and document:
- frontend file
- endpoint
- service
- repository/query
- validation
- derived calculations
- audit logging
- updated_by
- NULL handling

Student must consume canonical stored results.

## 4. Data Mapping

Verify:

student_subject_enrollment
+
student_subject_performance
+
student_semester_summary
+
students
→ Student performance view.

Document exact join keys and repeat-attempt handling.

## 5. Academic Calculation Rules

Separate:

### Canonical stored values
- total_marks
- percentage
- grade
- grade_point
- result_status

### Derived analytics
- trend
- strength/weakness
- gap
- priority

Do not silently recalculate or overwrite canonical Faculty values.

## 6. Component-Level Analysis

Plan how CT1/CT2/mid/end components can identify:
- consistently weak component
- significant decline
- missing component
- abnormal gap

Verify actual population of each column first.

NULL must not become zero.

## 7. Class Comparison

Plan privacy-safe comparison:
- class average
- percentile/rank only if approved
- minimum cohort size
- no exposure of other student identities

## 8. What-If / Marks Simulator

Plan deterministic calculations for:
- target marks
- target percentage
- grade scenarios
- SGPA scenarios

Simulator must never modify canonical marks.

## 9. API Plan

Inventory existing endpoints and classify:
- reuse
- extend
- new
- defer

## 10. UI Plan

Reuse existing:
- subject table
- academic cards
- charts
- subject details

Do not redesign global styles.

## 11. Analytics vs ML Boundary

Use deterministic logic for:
- total
- percentage
- grade
- SGPA/CGPA
- target marks
- exact what-if calculations

Identify future ML candidates:
- performance prediction
- trend prediction

Do not implement ML in MD-02 unless the repository plan explicitly requires it.

## 12. Acceptance Criteria

- Faculty-published marks appear for the correct student.
- Student cannot modify marks.
- Subject totals/grades use canonical data.
- Semester summaries are consistent.
- Repeat attempts are handled correctly.
- NULL components remain NULL.
- What-If does not alter real data.
- No duplicate marks table is created.
