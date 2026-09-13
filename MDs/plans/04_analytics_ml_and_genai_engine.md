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

## 9. Model Registry

The model registry is the system of record for every trained model that has been or could be used for production serving.

### 9.1 Registry Purpose

The registry exists to answer three questions at any point in the platform's life:

- Which model version is currently serving predictions?
- What training data, hyperparameters, and evaluation metrics produced that version?
- Which earlier versions exist and what were their evaluation outcomes?

Without a registry, serving relies on whichever model file happens to be present on disk, which makes rollback, comparison, and audit impossible.

### 9.2 Registry Tool

The blueprint specifies MLflow as the model registry. MLflow is chosen because it integrates with the Python ML stack already selected for training (Scikit-learn, XGBoost) and provides experiment tracking, artifact storage, and model versioning without requiring a separate infrastructure service.

### 9.3 Registry Contents

Each registered model version must record:

- Model type and algorithm (e.g. XGBoost classifier, logistic regression).
- Training data snapshot identifier (e.g. date range, ETL run ID, or row count hash).
- Hyperparameters used during training.
- Evaluation metrics (precision, recall, PR-AUC, and any threshold-dependent metrics).
- The decision threshold applied for classification (e.g. the at-risk cutoff).
- Registration timestamp.
- Promotion status (e.g. staging, production, archived).

### 9.4 Registry Rules

- Only models registered in the registry may be used for serving. Ad-hoc model files must not be loaded directly.
- The serving layer reads the current production-promoted model from the registry, not from a hardcoded file path.
- Archiving a model version does not delete it. Historical versions must remain available for audit and comparison.
- The registry is managed by FastAPI batch processes. Next.js has no direct interaction with the registry.

## 10. Model Versioning and Traceability

Versioning connects every prediction row in the warehouse back to the model that produced it.

### 10.1 Why Versioning Matters

A prediction or risk label that cannot be traced to its producing model is not auditable. If a faculty member questions why a student was flagged, the system must be able to identify the exact model version, the features that were used, and the evaluation context that justified putting that model into production.

### 10.2 Prediction-to-Model Link

Every row written to `Risk_Predictions` must reference:

- The model version identifier from the registry.
- The prediction timestamp.
- The feature snapshot or feature hash used as input.

This makes it possible to reproduce or explain a prediction months after it was generated, even if the model has been retrained multiple times since.

### 10.3 Versioning Lifecycle

1. A new model is trained and evaluated as part of a scheduled batch job.
2. If the evaluation meets the defined acceptance criteria, the model is registered and promoted to staging.
3. A manual or automated promotion step moves the model to production status in the registry.
4. The serving layer picks up the new production model on its next request cycle.
5. The previous production model is demoted to archived status but remains in the registry.

### 10.4 Rollback Discipline

If a newly promoted model produces unexpected results, the previous archived version can be re-promoted to production without retraining. The registry must support this without data loss or downtime in the serving layer.

## 11. Explainability

Explainability is a functional requirement, not a reporting convenience. Faculty need to understand why a student was flagged before they will trust and act on a prediction.

### 11.1 Explainability Method

The blueprint specifies SHAP (SHapley Additive exPlanations) as the primary explainability method. SHAP is chosen because it works naturally with the tree-based and linear models selected for this platform (XGBoost, logistic regression) and produces per-prediction feature contribution values.

### 11.2 What Explainability Must Provide

For each at-risk prediction, the system must be able to surface:

- The top contributing features (e.g. attendance percentage, backlog count, semester SGPA trend, lifestyle indicators).
- The direction and magnitude of each feature's contribution to the prediction.
- Enough context that a faculty member can understand the reasoning without reading model documentation.

### 11.3 Explainability Storage

Feature contribution values should be stored alongside the prediction output in the warehouse or in a linked explanation table. They must not be computed on-the-fly for every dashboard request, because SHAP computation can be expensive and the explanation for a given prediction is deterministic once the model and input are fixed.

### 11.4 Explainability in the UI

The UI document (file 05) defines how explanations are presented. This document defines what the backend must provide:

- A structured JSON response containing the prediction, the contributing features, and their SHAP values.
- A human-readable summary field that translates the top feature contributions into a short explanation sentence, generated during batch inference.

The UI may simplify or reformat this for presentation, but the backend must always retain the full explanation context.

### 11.5 Explainability Rules

- Predictions must never be served without an available explanation. If the explanation pipeline fails, the prediction should be flagged as unexplained rather than served without context.
- Explanations must reference the same model version as the prediction they accompany.
- The explanation format must remain stable across model retraining so the UI does not break when a new model version is deployed.

## 12. Faculty Feedback Loop

The feedback loop allows faculty to confirm, correct, or override a risk prediction. Without it, the model has no mechanism to learn from its own mistakes.

### 12.1 Why the Feedback Loop Exists

The original project brief describes predictions as one-way outputs. The blueprint identifies this as a gap: a model that flags students as at-risk but never receives confirmation or correction will never improve its precision or recall. Faculty are the domain experts closest to the student, and their judgment is the highest-quality label the system can collect.

### 12.2 Feedback Mechanism

Faculty should be able to perform the following actions through the faculty dashboard:

- Confirm a risk flag as accurate (the student is genuinely at risk).
- Dismiss a risk flag as inaccurate (the student is not at risk despite the prediction).
- Add a qualitative note explaining the reason for the confirmation or dismissal.

### 12.3 Feedback Storage

Feedback is stored in the warehouse and linked to the specific prediction row and model version it refers to. Each feedback record must capture:

- The faculty member who provided the feedback.
- The prediction row being evaluated.
- The feedback action (confirmed, dismissed).
- An optional note.
- The timestamp.

### 12.4 Feedback in Retraining

Confirmed and dismissed feedback becomes part of the labeled dataset for the next training cycle. The retraining pipeline should:

- Use confirmed flags as positive labels for the at-risk class.
- Use dismissed flags as negative labels or as signals to re-examine the feature contribution that led to the incorrect prediction.
- Track how much of the training set comes from faculty feedback versus the original label definition.

### 12.5 Feedback Rules

- Feedback must never modify the original prediction. The prediction row remains as-is for audit purposes; the feedback is a separate, linked record.
- Feedback is scoped to the faculty member's authorized students. A faculty member cannot provide feedback on a student they are not assigned to.
- Feedback volume and distribution should be visible in the admin dashboard as a platform health indicator.

## 13. Career Guidance Engine

The career guidance engine is a distinct module within the intelligence layer. It uses student performance, declared career preferences, and contextual data to produce grounded career-related recommendations.

### 13.1 Career Guidance Scope

The career guidance engine should answer questions such as:

- Given a student's academic performance and declared preferences, which career domains align well?
- Where are the gaps between the student's current skills and their stated career goals?
- What certifications, internships, or focus areas could strengthen the student's readiness?

### 13.2 Data Sources

The career guidance engine draws from:

- `Career_Preferences` — the student's declared domain, dream role, industry, certifications, and readiness level.
- `Subject_Performance` — actual academic outcomes across subjects and semesters.
- `Semester_Summary` — aggregate academic trajectory.
- `Subjects` — subject metadata including type, credits, and department alignment.
- `Lifestyle_Survey` — contextual signals such as study habits and part-time employment.

### 13.3 Career Guidance Output

The career guidance engine produces structured recommendations, not free-form text. Each recommendation should include:

- The recommended domain or action.
- The data points that support the recommendation.
- The student's current alignment score or gap assessment relative to their stated goal.

These structured outputs can then be passed to the GenAI layer for narrative generation if a human-readable summary is needed.

### 13.4 Career Guidance Rules

- Career guidance must be grounded in actual student data. Generic advice that does not reference the student's performance or preferences is not acceptable.
- The engine must not conflate performance prediction with career recommendation. A student may be academically strong but misaligned with their declared career goal, or vice versa.
- Career guidance is sensitive data and must follow the same role-scoping rules as other student-specific outputs.

### 13.5 Relationship to GenAI

The career guidance engine is not a GenAI module. It is a structured analytics and matching engine. GenAI may be used downstream to translate career guidance outputs into narrative summaries, but the matching logic itself must be deterministic and reproducible from the warehouse data.

## 14. RAG Readiness

The architecture anticipates Retrieval-Augmented Generation as a future capability for enriching GenAI insights with historical context.

### 14.1 What RAG Would Add

RAG would allow the GenAI layer to retrieve similar historical cases before generating a narrative. For example, when generating an at-risk summary for a current student, the system could retrieve past students with similar academic profiles and outcomes, and use those cases to ground the recommendation in observed institutional history.

### 14.2 Why RAG Is Not Required Now

The current warehouse already carries structured, versioned student history across semesters. The initial GenAI layer can ground its narratives in this structured data without a retrieval step. RAG becomes valuable when the volume of historical cases is large enough to support meaningful similarity-based retrieval and when the narrative quality would benefit from citing comparable past outcomes.

### 14.3 Architectural Readiness

The system is RAG-ready because:

- The warehouse schema already stores historical performance, risk predictions, and outcomes per student per semester.
- The GenAI adapter boundary (section 5) isolates the generation interface from the retrieval mechanism. Adding a retrieval step means extending the adapter, not restructuring the pipeline.
- The data model does not need to change to support RAG. The retrieval step queries existing warehouse tables using similarity or filtering criteria, then passes the retrieved context into the GenAI adapter alongside the current student's data.

### 14.4 RAG Readiness Rules

- RAG must not be implemented before the base GenAI layer is stable and producing grounded insights from structured data alone.
- When RAG is added, the retrieval step must be auditable. The system must log which historical cases were retrieved and passed to the GenAI provider for each generated insight.
- RAG does not change the grounding requirement. The generated insight must still be traceable to specific structured data, whether that data comes from the current student's record or from retrieved historical cases.

## 15. Cost Controls and Usage Governance

GenAI and ML operations have real, non-trivial costs that must be governed from day one rather than discovered at scale.

### 15.1 GenAI Cost Profile

GenAI narrative generation is the most expensive per-unit operation in the system. Each call to an external LLM provider incurs a cost based on token volume. Without governance, a dashboard that regenerates insights on every page view could produce unpredictable and unsustainable costs.

### 15.2 Cost Control Mechanisms

The following controls must be built into the system:

- **Batch generation over on-demand generation.** Insights should be generated on the ETL or retraining cadence and stored in the `GenAI_Insights` table. Dashboard requests should read pre-generated insights from the warehouse, not trigger new LLM calls.
- **Caching.** If on-demand generation is ever needed for specific use cases, the result must be cached and reused for subsequent requests for the same student and data snapshot.
- **Usage caps.** A configurable per-period cap on the number of GenAI API calls, enforced at the adapter layer. When the cap is reached, the system should serve the last cached insight with a staleness indicator rather than failing.
- **Token budget awareness.** The prompt construction logic should be aware of the provider's token limits and cost model. Prompts should include only the structured context needed for grounding, not unbounded data dumps.

### 15.3 ML Cost Profile

ML costs are lower per-unit than GenAI but can accumulate during retraining, especially as the student population and feature set grow. The main cost drivers are:

- Feature engineering computation during batch ETL.
- Model training time, especially for hyperparameter search.
- SHAP explanation computation during batch inference.

### 15.4 ML Cost Controls

- Retraining frequency should be tied to the data refresh cadence, not run more often than the data changes.
- Hyperparameter search should be bounded by a configurable time or iteration limit.
- SHAP computation should be batched and stored alongside predictions, not computed per-request.

### 15.5 Usage Monitoring

Both GenAI and ML usage must be observable:

- The admin dashboard should show GenAI call counts, token usage, and cost estimates per period.
- The admin dashboard should show retraining run frequency, duration, and model evaluation deltas.
- Alerts should fire if usage exceeds defined thresholds, before costs become a surprise.

### 15.6 Governance Rules

- Cost governance is a platform-level concern, not a module-level afterthought. The adapter layer and batch pipeline must enforce cost controls regardless of which module triggers the work.
- Cost controls must not silently degrade output quality. If a cap is reached or a budget is exhausted, the system must visibly indicate staleness or unavailability rather than serving nothing or serving outdated data without warning.
- Cost governance configuration should be environment-specific. Development and staging environments should have lower caps than production to prevent accidental cost during testing.
