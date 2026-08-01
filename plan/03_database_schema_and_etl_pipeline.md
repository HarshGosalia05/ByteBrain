# Database Schema and ETL Pipeline

## 1. Database Platform and Data Ownership

KenexAI KDAC-3 uses Supabase PostgreSQL as the persistent data layer and accesses it directly through the `pg` library. The project deliberately avoids Supabase REST and uses the database like a standard PostgreSQL system so the backend can remain portable and the access model can stay explicit.

This document defines how data should be organized, stitched, validated, and loaded so the rest of the platform can rely on a stable student-grain warehouse. It is the owning document for schema structure, identity resolution, and ETL behavior. It is not the place for UI, deployment, or predictive-model detail.

## 2. Core Schema Overview

The blueprint defines 14 core tables organized into four functional groups:

- Master data.
- Transactional / academic grain.
- Context data.
- Intelligence output.

The data model is student-centric. Every analytical path ultimately resolves around the student record, with supporting tables attached through the canonical `Student_ID` stitching key.

### 2.1 Core Table Set

| Functional Group               | Tables                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------- |
| Master data                    | `Departments`, `Students`, `Faculty`, `Subjects`                                      |
| Transactional / academic grain | `Student_Subject_Enrollment`, `Subject_Performance`, `Attendance`, `Semester_Summary` |
| Context data                   | `Lifestyle_Survey`, `Career_Preferences`, `Faculty_Student_Map`                       |
| Intelligence output            | `Risk_Predictions`, `GenAI_Insights`, `Users`                                         |

The table set reflects the project’s full data story: who the student is, what they study, how they perform, what context affects them, what the system predicts, and what narratives or guidance are produced from that information.

## 3. Student-Grain Data Model

The student-grain model is the central design concept for the warehouse.

### 3.1 Central Grain

The platform is designed so the analytical center of gravity is one row per student per subject per semester, with additional context joined in as needed.

That approach gives the system a consistent basis for:

- Subject-level performance analysis.
- Cohort-level comparisons.
- Attendance and performance correlation views.
- Risk prediction feature engineering.
- Career guidance grounded in actual student history.

### 3.2 Universal Stitching Key

`Student_ID` is the universal stitching key across all tables that describe a student. Source systems that do not natively carry `Student_ID` must be mapped to it during staging, not after the data has already been loaded into the warehouse.

The SQL seed files also carry `Enrollment_No` alongside `Student_ID` in the academic fact tables. In this implementation, `Enrollment_No` behaves as the repeated academic number, while `Student_ID` remains the stable student stitching key used to relate the same person across fact sets.

### 3.3 Academic Identifier Discipline

- Use `Student_ID` for cross-table stitching and person identity.
- Use `Enrollment_No` when preserving the academic numbering seen in the SQL fact rows.
- Do not collapse the two identifiers into a single term in the plan folder.

### 3.4 Grain Discipline

The warehouse should avoid mixing operational records and derived summaries at the same conceptual level.

- Raw or transactional facts belong in the transactional / academic grain.
- Derived summaries belong in `Semester_Summary`.
- Prediction outputs belong in `Risk_Predictions`.
- Narrative outputs belong in `GenAI_Insights`.

This separation prevents two sources of truth from forming around the same metric.

## 4. Master Data Layer

Master data provides the stable reference entities used throughout the platform.

### 4.1 Departments

Departments are the institutional grouping used for program-level organization and comparison.

Expected role in the warehouse:

- Anchor department-level reporting.
- Support departmental rollups and dashboards.
- Provide institutional structure for students and faculty.

### 4.2 Students

Students are the primary analytical subject of the platform.

Expected role in the warehouse:

- Represent the canonical person-level record.
- Carry the student identity used for stitching.
- Link out to academic, attendance, lifestyle, and career-related context.

### 4.3 Faculty

Faculty records represent the teaching or mentoring staff associated with students and subjects.

Expected role in the warehouse:

- Support advisory and mentorship relationships.
- Anchor faculty-facing dashboards and permissions.
- Provide the source entity for mentor mappings.

### 4.4 Subjects

Subjects are the academic units used for performance measurement and enrollment.

Expected role in the warehouse:

- Support subject-wise analytics.
- Anchor subject performance and enrollment records.
- Make it possible to compare subject outcomes across semesters or cohorts.

## 5. Transactional and Academic Grain

The transactional layer stores the operational academic facts that make the platform analytically useful.

### 5.1 Student_Subject_Enrollment

This table resolves the many-to-many relationship between students and subjects across semesters.

It is a stitching artifact as much as an academic record because it tells the platform which student was enrolled in which subject at which time. Historical enrollment must remain queryable even when a student changes subject load or semester context.

### 5.2 Subject_Performance

This table stores subject-level marks or performance outcomes.

It is the main factual source for subject performance analytics and one of the key inputs into summary tables and predictive features.

### 5.3 Attendance

This table stores attendance-related facts.

It is important because attendance is one of the operational signals that can correlate with performance decline or risk behavior.

### 5.4 Semester_Summary

This is a derived table, not a manually maintained source of truth.

It is populated by ETL from `Subject_Performance` and `Attendance` so the system has a clean aggregated view at the semester level. The blueprint is explicit that this table must not be maintained independently, because derived summaries should be reproducible from the underlying fact tables.

### 5.5 Transactional Design Rules

- Keep academic facts at their natural grain.
- Preserve semester history rather than overwriting old values.
- Derive summary data from source facts instead of editing it manually.
- Ensure the same underlying fact can support both analytics and ML feature creation.

## 6. Context Data Layer

Context data helps the platform interpret the student beyond raw academic performance.

### 6.1 Lifestyle_Survey

This table stores lifestyle and self-reported context.

The blueprint treats this as sensitive data because it may influence student interpretation without being purely academic. It should therefore be carefully scoped and only exposed to the roles that are entitled to see it.

### 6.2 Career_Preferences

This table stores declared career interests or preferences.

Its purpose is to ground career guidance in what the student actually wants, rather than in generic advice or a subject-only interpretation of performance.

### 6.3 Faculty_Student_Map

This table resolves the mentor or advisor relationship between faculty and students.

Like enrollment, it is a first-class stitching artifact because relationships can change over time and must remain historically queryable.

### 6.4 Context Data Design Rules

- Treat context data as part of the student record, not as optional decoration.
- Preserve time or semester versioning where relationship history matters.
- Apply access scoping because context data is often more sensitive than aggregate performance.
- Do not silently widen visibility beyond the roles that are entitled to the data.

## 7. Intelligence Output Layer

The intelligence output layer records what the platform has concluded from the warehouse and model pipeline.

### 7.1 Risk_Predictions

This table stores versioned at-risk predictions or performance forecasts.

The blueprint is explicit that every row must remain auditable, which means each prediction should be traceable to the model version and training context that produced it. This table is not merely a cache of latest predictions; it is an historical record of model output.

### 7.2 GenAI_Insights

This table stores narrative insight outputs generated from structured data and model results.

The key requirement is grounding. These insights must be reproducible from the structured source context and must remain auditable so that the platform can show what data informed the narrative.

### 7.3 Users

This table supports authentication and role resolution in the current implementation.

It is part of the intelligence output group in the blueprint’s schema grouping, but operationally it is also the bridge between authentication and the rest of the system. It remains important to keep it under explicit application control rather than broadening it into an implicit identity layer spread across the codebase.

### 7.4 Intelligence Output Rules

- Keep model outputs versioned.
- Keep generated narratives grounded in structured source data.
- Preserve the record of which model or pipeline version produced a result.
- Do not treat outputs as ephemeral if they influence student intervention or faculty action.

## 8. Multi-Tenancy Readiness

The blueprint requires multi-tenancy readiness from day one, even if only one institution exists initially.

### 8.1 Why Tenancy Belongs in the Schema

If tenancy is left until later, the team will eventually need to retrofit isolation, filtering, and possibly partitioning into already-populated tables. That is materially more expensive than including the tenancy dimension early.

### 8.2 Schema Expectation

Every core table should be compatible with an institution or tenant identifier.

This does not mean the system must act as a full multi-tenant SaaS on day one. It means the schema must be able to grow into that model without a structural rewrite.

### 8.3 Design Principle

Treat tenant identity as a core architectural axis, not as a later reporting convenience.

## 9. ETL Pipeline Architecture

The ETL pipeline is the mechanism that turns raw institutional data into a trustworthy warehouse.

### 9.1 Pipeline Stages

The blueprint defines the ETL flow as:

1. Extract.
2. Validate and stage.
3. Stitch.
4. Load.
5. Derive.

### 9.2 Extract

The extract stage pulls from raw sources such as exam records, attendance logs, survey exports, and career-preference forms.

At this stage, the system should still preserve source identity and avoid forcing an incomplete transformation too early.

### 9.3 Validate and Stage

Validation occurs before anything reaches the warehouse.

Records with schema problems, missing critical values, or other quality failures should be quarantined and logged rather than silently discarded. The goal is observability, not hidden data loss.

### 9.4 Stitch

Stitching joins the source data around `Student_ID` and resolves identity conflicts explicitly.

This stage is the most critical technical risk in the data pipeline because a wrong identity match will contaminate every downstream view, prediction, and narrative.

### 9.5 Load

The load stage writes validated and stitched data into the warehouse schema.

The warehouse should receive cleanly structured, relationally consistent data rather than raw source fragments.

### 9.6 Derive

The derive stage computes summary or aggregate tables such as `Semester_Summary` from the loaded fact data.

This stage keeps the warehouse analytically useful without requiring every dashboard query to reconstruct the same logic repeatedly.

## 10. Data Stitching and Identity Resolution

Data stitching is the heart of the platform’s trust model.

### 10.1 Why Stitching Is a First-Class Concern

The platform depends on combining academic, attendance, lifestyle, and career data into one coherent student view. If identity resolution is wrong, the system may produce analytics and predictions that look plausible but are silently incorrect.

### 10.2 Canonical Identity Rules

- `Student_ID` is the canonical key.
- Mapping to `Student_ID` happens during staging.
- Source systems that lack `Student_ID` require an explicit mapping step.
- Matching confidence or method should be logged.
- Ambiguous or unmatched records should be routed to review rather than force-matched.

### 10.3 Bridge Tables

The blueprint explicitly identifies two bridge tables that deserve first-class treatment:

- `Student_Subject_Enrollment`.
- `Faculty_Student_Map`.

Both should preserve historical relationship changes over time so that past enrollments and mentorship structures remain queryable after reassignment.

### 10.4 Stitching Integrity Rules

- Never use silent fuzzy matching as the default behavior for identity-critical records.
- Never drop ambiguous records without traceability.
- Never overwrite relationship history when a new term or mapping appears.

## 11. Data Quality, Auditability, and Refresh Discipline

The warehouse should be designed for correctness and traceability, not just for storage.

### 11.1 Validation Expectations

The ETL pipeline should validate schema alignment, basic integrity, and completeness before loading data.

### 11.2 Audit Expectations

The warehouse must support historical review of:

- When data was ingested.
- Which source produced it.
- Which pipeline version transformed it.
- Which model version produced a prediction.
- Which context supported a narrative insight.

### 11.3 Refresh Discipline

The blueprint assumes batch updates rather than real-time mutation for most academic data.

That means downstream consumers should expect freshness indicators, not immediate source-system mirroring. The architecture should be resilient to slightly stale but known data rather than fragile and over-coupled to live pipeline timing.

## 12. How This Document Relates to Other Plan Files

This file is the authority for the database model and ETL behavior. It depends on the architecture file for service boundaries, but it should not re-explain those boundaries in detail.

Use this document to answer questions such as:

- What tables exist?
- What is the central grain of the data model?
- How do source systems become unified student records?
- How are summary tables derived?
- How does the warehouse stay auditable?
- What makes the schema ready for future tenancy?

For the service split, contract rules, and client-boundary decisions, refer to the architecture document. For analytics, ML, or GenAI behavior, refer to the intelligence document that will follow.
