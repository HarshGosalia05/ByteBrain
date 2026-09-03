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

# MD-08 — ML + GENAI INTELLIGENCE

## 1. Objective

Introduce predictive ML and grounded GenAI only after the Student Module has reliable academic, attendance, career, and analytics foundations.

Dependencies:
MD-01 through MD-07 as required.

## 2. FIRST TASK — CLASSIFY EVERY INTELLIGENCE FEATURE

For each proposed feature classify:

- deterministic
- rule-based
- statistical
- ML
- GenAI

Do not use ML or GenAI where deterministic logic is authoritative and sufficient.

## 3. ML USE CASES

Potential models:

### A. At-Risk Prediction
Inputs may include:
- student history
- enrollment
- performance
- attendance
- semester summary
- governed contextual data if justified

Output:
- probability
- risk level
- model version
- prediction timestamp
- feature snapshot
- explanation

### B. Performance Prediction
Potential inputs:
- historical semester performance
- current component marks
- attendance
- credits
- subject history

### C. Trend Prediction
Potential:
- future academic trajectory
- cohort trends

### D. Attendance Forecast
Only if sufficient historical data exists.

## 4. DATASET COMBINATION ANALYSIS

For EACH model provide:

TABLE A
+
TABLE B
+
TABLE C
↓
JOIN KEY
↓
DATA GRAIN
↓
FEATURE ENGINEERING
↓
TARGET
↓
MODEL
↓
PREDICTION
↓
STORAGE
↓
API
↓
UI

Verify:
- student_id
- enrollment_record_id
- semester
- subject
- academic year

Do not create a model using accidental duplicate rows.

## 5. LEAKAGE PREVENTION

Use time-aware validation where appropriate.

Do not allow future semester information into a historical prediction.

Do not mix student records across train/test in a way that causes identity leakage.

Document:
- train
- validation
- test
- temporal split
- cohort split

## 6. MODEL COMPARISON

For classification consider:
- Logistic Regression baseline
- Random Forest
- XGBoost if justified

For regression consider:
- Linear/ElasticNet baseline
- Random Forest/Gradient Boosting/XGBoost if justified

Do not assume XGBoost wins.

Use appropriate metrics:
- precision
- recall
- F1
- PR-AUC
- MAE/RMSE for regression
- calibration where needed

## 7. SMALL DATASET RULE

Inspect actual row counts and data coverage before model selection.

If the dataset is too small:
- state limitations
- prefer simple baselines
- avoid overclaiming accuracy
- consider collecting more historical data

## 8. EXPLAINABILITY

Use SHAP where appropriate.

Prediction should be paired with:
- top factors
- feature values
- direction/impact
- model version

Do not show unexplained risk predictions.

## 9. MODEL STORAGE

Inspect existing `risk_predictions`.

Determine whether existing schema can support:
- probability
- risk level
- model version
- prediction timestamp
- feature snapshot
- explanation

Only propose schema changes if genuinely required.

## 10. GENAI ARCHITECTURE

GenAI input:

Verified structured facts
+
Analytics
+
ML prediction
+
SHAP explanation
+
Career profile where applicable

GenAI output:
- academic explanation
- study plan
- action plan
- career explanation
- Q&A
- mentor summary
- faculty insight

## 11. GENAI RULES

GenAI must NOT:
- calculate authoritative marks
- calculate authoritative attendance
- determine eligibility
- invent grades
- invent student data
- override ML/rules
- directly write academic records
- expose unauthorized student information

GenAI is a narrative/explanation layer.

## 12. GROUNDING

Before calling the model:

Database
→ verified backend context
→ analytics
→ ML/SHAP
→ prompt/context builder
→ GenAI

Do not allow the LLM to directly query arbitrary SQL.

## 13. PROVIDER ADAPTER

Inspect existing GenAI infrastructure.

If required, plan:

GenAI Service
→ Grounding
→ Prompt Builder
→ Provider Adapter
→ Model Provider

Keep provider-specific SDK logic isolated.

## 14. PROMPT VERSIONING

Plan storage/traceability for:
- prompt version
- model/provider
- input snapshot
- output
- timestamp
- source context

## 15. COST/SAFETY

Plan:
- batch generation where possible
- caching
- token limits
- rate limits
- retry strategy
- failure fallback
- no repeated generation on every page refresh

## 16. RAG

Do not introduce RAG automatically.

First determine whether structured PostgreSQL context is sufficient.

If RAG is needed later, identify:
- documents
- historical cases
- retrieval keys
- embedding strategy
- access controls
- grounding requirements

## 17. Student UI

Plan:
- risk explanation
- performance prediction
- AI academic coach
- action plan
- career explanation

Keep predictions clearly labeled as predictions.

## 18. Faculty/Mentor UI

Plan:
- at-risk students
- explanation
- intervention context
- mentor-ready summary
- faculty insight

Do not expose student data beyond authorized scope.

## 19. Acceptance Criteria

- Every ML feature has a justified dataset.
- Dataset joins are verified.
- No leakage is introduced.
- Model metrics are recorded.
- Predictions are explainable.
- Student predictions are read-only.
- GenAI uses grounded structured context.
- GenAI cannot modify academic records.
- Provider-specific code is isolated.
- RAG is only introduced if justified.
- Existing Student/Faculty functionality remains intact.
