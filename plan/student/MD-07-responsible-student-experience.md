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

# MD-07 — RESPONSIBLE STUDENT EXPERIENCE

## 1. Objective

Add privacy, consent, accessibility, localization, and responsible student-control features without weakening academic security.

## 2. Scope

Plan:
- consent dashboard
- privacy controls
- data visibility
- data export
- deletion request
- institutional research consent
- privacy-safe class comparison
- guardian sharing
- English/Hindi/Gujarati
- Data Saver
- accessibility
- emergency information
- authorized-staff-only emergency access
- wellness check-in
- non-clinical support

## 3. Privacy Audit

Inspect:
- authentication
- authorization
- role system
- RLS
- API ownership
- caching
- logging
- sensitive field access

## 4. Consent

Separate:
- academic system operation
- optional research use
- optional guardian sharing
- optional personalization

Do not make optional consent silently mandatory.

## 5. Sensitive Data

Inspect `lifestyle_survey` and any wellbeing-related fields.

Plan strict access boundaries.

Do not:
- diagnose
- infer medical conditions
- expose sensitive data in class comparison
- send sensitive information to GenAI unnecessarily

## 6. Data Export/Delete

Determine actual legal/system requirements and existing repository capabilities.

If no existing infrastructure exists, mark as a future implementation dependency rather than inventing a solution.

## 7. Accessibility

Inspect current UI and plan:
- keyboard navigation
- semantic labels
- focus
- contrast
- screen-reader support
- reduced-motion considerations

Do not change global CSS.

## 8. Localization

Determine current i18n infrastructure.

Do not implement translation by hardcoding a second UI.

## 9. Data Saver

Plan:
- reduced chart payload
- deferred noncritical calls
- image optimization
- optional realtime disable
- pagination

## 10. Acceptance Criteria

- Sensitive data is protected.
- Student controls are explicit.
- Academic data remains read-only.
- Optional consent is not silently forced.
- Accessibility uses existing design patterns.
- global.css is untouched.
