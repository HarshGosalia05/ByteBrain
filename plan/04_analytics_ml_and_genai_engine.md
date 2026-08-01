# Analytics, ML, and GenAI Engine

## 1. Purpose

This document defines how the intelligence layer should turn warehouse data into descriptive analytics, predictive scoring, and grounded narrative guidance. It is intentionally separate from the architecture document because it owns the behavior of the analysis pipeline, not the service boundary itself.

The core rule is simple: FastAPI owns the intelligence layer, PostgreSQL supplies the structured data, and Next.js only presents the results.

## 2. Intelligence Layer Scope

The intelligence layer has three distinct outputs:

- Analytics: explain what happened or what is true now.
- ML: estimate risk or future outcomes.
- GenAI: generate grounded narratives from structured facts and model output.

These outputs are related, but they are not interchangeable. A dashboard can show all three, but each output must remain independently traceable.

## 3. Analytics

Analytics is the descriptive layer.

It should answer questions such as:

- How is a student performing across semesters?
- Which subjects or cohorts are trending up or down?
- What attendance or backlog patterns correlate with weaker outcomes?
- Which faculty-student or context signals are most relevant for review?

### 3.1 Required Properties

- Analytics must be derived from loaded warehouse data, not handwritten in the UI.
- Analytics must be reproducible from the same source snapshot.
- Analytics should be suitable for student, faculty, and admin dashboards.

### 3.2 Output Shape

Analytics outputs should be structured enough for UI composition, filtering, and explanation. They should not be free-form text by default.

## 4. Machine Learning

ML is the predictive layer.

Its job is to score or classify risk using academic, attendance, and context features. The blueprint requires this layer to be batch-oriented and decoupled from online serving.

### 4.1 ML Responsibilities

- Feature engineering from stitched student data.
- Model training and evaluation.
- Batch inference for risk or related predictions.
- Versioned prediction output with provenance.

### 4.2 ML Rules

- Training must happen offline.
- Serving must use the latest approved model version, not an implicit local notebook state.
- Prediction tables must remain auditable and historical.
- Features should be grounded in the warehouse rather than raw source fragments.

### 4.3 Risk Output Discipline

Risk scores should be explainable in terms of contributing signals such as attendance, backlog, semester performance, and contextual indicators. The UI may simplify this for presentation, but the backend must retain the richer explanation context.

## 5. GenAI

GenAI turns structured data and model results into readable guidance.

The system is provider-agnostic, so the LLM vendor can change without changing the rest of the platform contract.

### 5.1 GenAI Responsibilities

- Generate student-facing summaries.
- Generate faculty-facing intervention narratives.
- Translate structured analytics into plain language.
- Stay grounded in retrieved facts and model outputs.

### 5.2 GenAI Rules

- Never generate advice without source grounding.
- Never treat the provider output as authoritative on its own.
- Keep the adapter layer isolated from the rest of the codebase.
- Preserve prompt, source, and response traceability where practical.

## 6. Data-to-Insight Flow

The recommended flow is:

1. Load and stitch warehouse data.
2. Build descriptive analytics.
3. Derive ML features and predictions.
4. Retrieve supporting facts for a target user or cohort.
5. Generate grounded narrative insight.
6. Return structured results to the UI.

This sequence keeps the outputs consistent and makes it easier to debug a bad recommendation later.

## 7. Layer Boundaries

- Next.js must not calculate risk or generate insights.
- FastAPI must own feature engineering, model logic, and GenAI orchestration.
- PostgreSQL must remain the durable store for inputs, outputs, and audit trails.

## 8. Quality Expectations

- Every prediction should be traceable to a model version.
- Every insight should be traceable to the structured context that informed it.
- Every analytics endpoint should behave deterministically for a given data snapshot.
- The system should degrade gracefully if a downstream model or provider is unavailable.
