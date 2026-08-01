# Delivery Roadmap, Quality, and Operations

## 1. Purpose

This document defines how the project should be delivered, validated, and operated. It turns the architecture and domain plan into a practical sequence of work with quality gates.

## 2. Delivery Philosophy

The project should be built backend-first, then API-first, then UI-first for each module. That order matches the current repository state and avoids polishing screens before the underlying behavior is ready.

## 3. Recommended Module Order

1. Core data and identity foundations.
2. ETL and stitching pipeline.
3. Descriptive analytics APIs.
4. ML feature generation and batch predictions.
5. Grounded GenAI insight generation.
6. Role-specific dashboard completion.
7. Operational hardening and deployment readiness.

## 4. Definition of Done

A module should not be treated as complete until all of the following are true:

- The backend behavior exists.
- The response shape is stable.
- The UI consumes the verified contract.
- The main failure states are handled.
- The output is auditable or explainable where appropriate.

## 5. Quality Gates

### 5.1 Functional Validation

- Verify the feature behaves correctly end to end.
- Check the relevant route, API, or data pipeline with realistic inputs.
- Confirm that role boundaries are preserved.

### 5.2 Data Quality

- Validate schema expectations before load.
- Quarantine bad records instead of silently dropping them.
- Preserve lineage from source to warehouse to output.

### 5.3 Model Quality

- Track model version, training context, and inference time.
- Review prediction stability and obvious failure modes.
- Keep offline training separated from live serving.

### 5.4 UI Quality

- Check responsive behavior.
- Check loading, empty, and error states.
- Confirm the dashboard still communicates clearly when data is partial.

## 6. Operational Expectations

- Keep observability visible at the service and pipeline level.
- Preserve logs or metadata that help trace bad outputs.
- Use controlled batch jobs for ETL, derivation, and retraining.
- Prefer graceful degradation over hard failure when a non-critical dependency is unavailable.

## 7. Change Management

When implementation changes, update the owning plan document first, then propagate any downstream wording that depends on it.

That rule keeps the plan folder usable for both humans and coding agents, because each file remains a stable reference rather than a moving target.

## 8. Risk Management

The main delivery risks are:

- Identity mismatches during stitching.
- Data quality problems in source feeds.
- Overlapping logic between Next.js and FastAPI.
- Prediction outputs without clear provenance.
- UI completion getting ahead of backend readiness.

The roadmap should reduce these risks by sequencing work in the right order and by requiring validation at each stage.
