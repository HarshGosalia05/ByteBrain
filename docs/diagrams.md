# KenexAI Architecture and Workflow Diagrams

Short explanations accompany each diagram. Labels describe current implementation unless marked **PLANNED / FUTURE**.

## 1. System Architecture Diagram

```mermaid
flowchart LR
  U[Student / Faculty / Admin] --> N[Next.js App Router]
  N --> BFF[Next.js BFF route handlers]
  BFF --> API[FastAPI /api/v1]
  API --> AUTH[Bearer identity and role dependencies]
  AUTH --> SVC[Role services and repositories]
  SVC --> DB[(PostgreSQL-compatible database)]
  SVC --> ML[ML prediction services]
  ML --> ART[M1-M3 joblib artifacts]
  ML --> M4[M4 deterministic rule engine]
  SVC --> EXP[ML-08 grounded explanations]
  API --> CHAT[ChatOrchestrator]
  CHAT --> TOOLS[IntentRouter + ToolRegistry + role tools]
  TOOLS --> VC[VerifiedContext]
  VC --> G0[GenAIService]
  G0 --> PROVIDER[OpenAI-compatible provider]
```

The frontend reaches role services through BFF routes; ML and GenAI remain backend boundaries.

## 2. High-Level Data Flow Diagram

```mermaid
flowchart LR
  RAW[Academic, attendance, career and lifestyle records] --> DB[(Database)]
  DB --> ANA[Deterministic analytics]
  DB --> FE[ML feature preparation]
  FE --> MODELS[M1 / M2 / M3 inference]
  DB --> RULES[M4 rule inputs]
  RULES --> M4[M4 readiness score]
  MODELS --> PRED[Typed predictions]
  M4 --> PRED
  PRED --> STORE[ml_predictions]
  PRED --> EXPL[ML-08 explanation]
  ANA --> UI[Role APIs and UI]
  EXPL --> UI
```

## 3. Student Module Workflow

```mermaid
flowchart TD
  S[Student login] --> DASH[Student dashboard]
  DASH --> ACAD[Academic summary and performance]
  DASH --> ATT[Attendance]
  DASH --> SUB[Subjects and report card]
  DASH --> ML[ML insights and explanations]
  DASH --> CAREER[Career readiness and alignment]
  DASH --> GOALS[Goals, health, priorities and notifications]
  DASH --> CHAT[Grounded student chat]
```

The student paths use the authenticated student identity and own-data scope.

## 4. Faculty Module Workflow

```mermaid
flowchart TD
  F[Faculty login] --> FD[Faculty dashboard]
  FD --> GROUPS[Classes and mentees]
  GROUPS --> STUDENT[Authorized student]
  STUDENT --> PROFILE[Profile / overview]
  STUDENT --> INSIGHTS[ML insights]
  INSIGHTS --> REVIEW[M3 review]
  REVIEW --> DECIDE{Confirm or dismiss}
  DECIDE --> FB[(prediction_feedback)]
  FD --> OPS[Subjects, marks, attendance, performance, workload]
```

Faculty scope is checked before student-specific data, prediction, or feedback operations.

## 5. Admin Module Workflow

```mermaid
flowchart TD
  A[Admin login] --> AD[Admin dashboard]
  AD --> AC[Academic and department analytics]
  AD --> AT[Attendance intelligence]
  AD --> RISK[Deterministic risk register]
  AD --> PEOPLE[Students and faculty]
  AD --> ML[ML intelligence and feedback health]
  AD --> EXEC[Executive summary and announcements]
```

## 6. Authentication and RBAC Flow

```mermaid
sequenceDiagram
  participant User
  participant Next as Next.js login action
  participant DB as users table
  participant API as FastAPI
  participant Scope as Role/scope dependency

  User->>Next: username + password
  Next->>DB: active credential lookup
  DB-->>Next: role + linked identity
  Next-->>User: HTTP-only session cookie and role redirect
  User->>API: Bearer session JSON payload
  API->>API: parse JSON/base64 identity
  API->>Scope: require Student/Faculty/Admin
  Scope-->>API: role accepted or 403
  API-->>User: protected response
```

The current integration uses a plaintext JSON session payload; JWT is **PLANNED / FUTURE**.

## 7. Database ER Diagram

```mermaid
erDiagram
  DEPARTMENTS ||--o{ STUDENTS : contains
  DEPARTMENTS ||--o{ FACULTY : contains
  STUDENTS ||--o{ STUDENT_SUBJECT_ENROLLMENT : enrolls
  SUBJECTS ||--o{ STUDENT_SUBJECT_ENROLLMENT : offered_as
  STUDENT_SUBJECT_ENROLLMENT ||--o| STUDENT_SUBJECT_PERFORMANCE : has
  STUDENTS ||--o{ STUDENT_SEMESTER_SUMMARY : has
  STUDENTS ||--o{ DAILY_ATTENDANCE_07 : records
  FACULTY ||--o{ FACULTY_STUDENT_MAP : scopes
  STUDENTS ||--o{ FACULTY_STUDENT_MAP : assigned
  STUDENTS ||--o| CAREER_PREFERENCES : declares
  STUDENTS ||--o| LIFESTYLE_SURVEY : reports
  STUDENTS ||--o{ RISK_PREDICTIONS : receives
  STUDENTS ||--o{ ML_PREDICTIONS : receives
  ML_PREDICTIONS ||--o{ PREDICTION_FEEDBACK : reviewed_by
  FACULTY ||--o{ PREDICTION_FEEDBACK : submits
  STUDENTS ||--o{ STUDENT_MESSAGES : receives
  STUDENTS ||--o{ STUDENT_GOALS : owns
  USERS }o--o| STUDENTS : links
  USERS }o--o| FACULTY : links
```

The diagram shows runtime relationships evidenced by SQL/service usage; complete foundational DDL/RLS state is **NOT VERIFIED**.

## 8. ETL and Data Pipeline

```mermaid
flowchart LR
  SOURCE[CSV / seeded academic data] --> ETL[backend/etl extraction and validation]
  ETL --> TABLES[(Database tables)]
  TABLES --> REPO[Repositories]
  REPO --> SERVICES[Analytics and ML services]
  SERVICES --> UI[Role APIs / UI]
```

The repository contains ETL code and generated datasets. A deployed warehouse orchestration is **NOT VERIFIED**.

## 9. ML Pipeline

```mermaid
flowchart LR
  DATA[(Database data)] --> FETCH[Model-specific fetch]
  FETCH --> CONTRACT[Feature contract and encoding]
  CONTRACT --> LOAD[Registry artifact loader]
  LOAD --> INF[InferenceService]
  INF --> RESULT[Typed PredictionResult]
  RESULT --> PERSIST[Optional ml_predictions persistence]
  RESULT --> EXPLAIN[ML-08 explanation]
```

## 10. M1-M4 Architecture

```mermaid
flowchart TD
  INPUT[Verified database inputs] --> M1[M1 regression: end-sem marks]
  INPUT --> M2[M2 regression: next-sem percentage + SGPA]
  INPUT --> M3[M3 classification: next-sem at-risk 0/1]
  INPUT --> M4[M4 deterministic score: career readiness 0-100]
  M1 --> OUT[Typed model outputs]
  M2 --> OUT
  M3 --> OUT
  M4 --> OUT
```

M1-M3 use joblib artifacts. M4 is explicitly rule-based and has no required trained artifact.

## 11. ML Prediction Lifecycle

```mermaid
stateDiagram-v2
  [*] --> InputsFetched
  InputsFetched --> FeaturesPrepared
  FeaturesPrepared --> Inference
  Inference --> TypedResult
  TypedResult --> Persisted: generation/persistence path
  TypedResult --> Served: read-only prediction path
  Persisted --> Retrieved
  Retrieved --> Explained
  Served --> Explained
  Explained --> Presented
  Presented --> [*]
```

## 12. ML-08 Explainability Flow

```mermaid
flowchart LR
  PRED[Already-produced prediction] --> ES[ExplanationService]
  INPUTS[Actual consumed inputs] --> ES
  META[Registry metadata] --> ES
  RULES[Documented business rules] --> ES
  ES --> STRUCT[Structured grounded explanation]
  STRUCT --> UI[Role-specific UI / GenAI context]
  ES -. omits .-> UNSUPPORTED[Confidence, probability, feature importance]
```

## 13. ML-12 Feedback Loop

```mermaid
flowchart LR
  FAC[Faculty] --> VIEW[Authorized student ML Insights]
  VIEW --> M3[M3 prediction]
  M3 --> DEC{Confirm / Dismiss}
  DEC --> FB[(prediction_feedback append-only)]
  FB --> RES[Feedback label resolution]
  RES --> LABEL[confirmed=1, dismissed=0]
```

## 14. ML-13 Retraining Loop

```mermaid
flowchart TD
  HIST[Historical M3 records] --> COMBINE[Combine with resolved faculty labels]
  FB[(prediction_feedback)] --> RESOLVE[latest_verdicts]
  RESOLVE --> COMBINE
  COMBINE --> VALIDATE[Feature and sample safety gates]
  VALIDATE --> CV[Stratified 5-fold pipeline evaluation]
  CV --> TRAIN[Balanced classifier retraining]
  TRAIN --> ART[Canonical M3 joblib artifact]
  ART --> RELOAD[Reload and serving verification]
  RELOAD --> SERVE[PredictionService]
```

## 15. GenAI Architecture

```mermaid
flowchart LR
  CHAT[Chat API] --> ORCH[ChatOrchestrator]
  ORCH --> ROUTER[IntentRouter]
  ROUTER --> REG[ToolRegistry]
  REG --> TOOL[Role-specific implemented tool]
  TOOL --> CONTEXT[VerifiedContext]
  CONTEXT --> SERVICE[GenAIService]
  SERVICE --> ADAPTER[OpenAICompatibleProvider]
  ADAPTER --> LLM[Configured external model]
  LLM --> RESPONSE[Normalized ChatResponse]
```

## 16. GenAI Grounding Flow

```mermaid
sequenceDiagram
  participant User
  participant Router as IntentRouter
  participant Tool as Authorized tool
  participant Context as VerifiedContext
  participant G0 as GenAIService
  participant LLM as Provider model

  User->>Router: natural-language question
  Router->>Router: role-scoped deterministic classification
  Router->>Tool: allowlisted tool call
  Tool->>Context: structured verified data + source/scope
  Context->>G0: context-only request
  G0->>LLM: grounding instruction + context + bounded history
  LLM-->>G0: narrative completion
  G0-->>User: normalized response
```

The LLM does not receive arbitrary SQL, a database pool, or model artifacts.

## 17. GenAI Student Flow

```mermaid
flowchart TD
  S[Student question] --> AUTH[Authenticated Student identity]
  AUTH --> ROUTE[Student intent]
  ROUTE --> TOOL[Academic / attendance / subject / prediction / career tool]
  TOOL --> CTX[Own-student VerifiedContext]
  CTX --> G0[GenAIService]
  G0 --> ANSWER[Grounded student guidance]
```

## 18. GenAI Faculty Flow

```mermaid
flowchart TD
  F[Faculty question] --> AUTH[Authenticated Faculty identity]
  AUTH --> RESOLVE[Resolve target within faculty scope]
  RESOLVE --> ROUTE[Faculty intent]
  ROUTE --> TOOL[Student / subject / flagged / prediction / department tool]
  TOOL --> CTX[Scoped VerifiedContext]
  CTX --> G0[GenAIService]
  G0 --> ANSWER[Grounded faculty guidance]
```

## 19. GenAI Admin Flow

```mermaid
flowchart TD
  A[Admin question] --> AUTH[Authenticated Admin identity]
  AUTH --> ROUTE[Admin intent]
  ROUTE --> TOOL[Institution / department / trends / flagged / ML tool]
  TOOL --> CTX[Institution-scope VerifiedContext]
  CTX --> G0[GenAIService]
  G0 --> ANSWER[Grounded administrative guidance]
```

## 20. Complete End-to-End KenexAI Workflow

```mermaid
flowchart TD
  USER[Student / Faculty / Admin] --> LOGIN[Login and session]
  LOGIN --> UI[Role-specific Next.js UI]
  UI --> BFF[BFF route]
  BFF --> API[FastAPI protected API]
  API --> DB[(Academic database)]
  DB --> ANALYTICS[Deterministic analytics]
  DB --> PREDICT[ML feature fetch and M1-M3 inference]
  DB --> READINESS[M4 deterministic readiness]
  PREDICT --> STORE[(ml_predictions)]
  STORE --> EXPLAIN[ML-08 explanation]
  UI --> CHAT[Chat request]
  CHAT --> ROUTE[Intent and allowlisted tool]
  ROUTE --> VERIFIED[VerifiedContext]
  VERIFIED --> LLM[GenAI provider]
  LLM --> UI
  FAC[Faculty review] --> FEEDBACK[(prediction_feedback)]
  FEEDBACK --> RETRAIN[Offline ML-13 retraining]
  RETRAIN --> PREDICT
```

This is the complete current flow; automated deployment, MLflow promotion and scheduled retraining would be **PLANNED / FUTURE**.
