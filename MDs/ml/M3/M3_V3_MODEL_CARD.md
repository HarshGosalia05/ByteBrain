# M3 v3 Model Card — Same-Semester End-Term Academic Risk Classifier

## Model Overview
- **Model Identifier**: `m3_v3_endterm_risk`
- **Model Version**: `3.0`
- **Model Type**: Supervised Binary Classification
- **Architecture**: `HistGradientBoostingClassifier` (scikit-learn) with embedded `M3V3Preprocessor` (median imputation)
- **Primary Task**: Estimate whether a student will enter an academic-risk state (fail $\ge 1$ course or receive ATKT backlog) at the conclusion of the **same academic semester**, evaluated after mid-semester exams.
- **Trained Artifact**: `artifacts/models/m3_v3_endterm_risk.joblib`

---

## Intended Use & Scope
- **Target User**: Academic advisors, faculty mentors, and students.
- **Decision Point**: Mid-semester milestone ($T$).
  - BBA: Semester 5 Mid-Sem $\rightarrow$ Semester 5 End-Term
  - CSE: Semester 7 Mid-Sem $\rightarrow$ Semester 7 End-Term
- **Actionable Goal**: Enable proactive academic tutoring and mentoring interventions before final exams take place.
- **Out of Scope & Restrictions**:
  - Punitive academic actions or automated expulsion decisions.
  - Forward cross-semester predictions ($T \rightarrow T+1$), which are covered separately by M3 v2.
  - Final-semester students with no upcoming standard end-term exams (e.g. 8th semester internship).

---

## Training Data & Cohort
- **Cohort**: CSE 6A cohort consisting of 1,200 individual students tracked longitudinally over Semesters 1 through 7.
- **Dataset Size**: 8,400 semester instances (7,200 training instances, 1,200 held out temporally).
- **Target Distribution**:
  - Total Positives: 227 (2.70% base rate)
  - Total Negatives: 8,173 (97.30%)
  - Unique Students with At-Risk Episodes: 179
- **Imbalance Mitigation**: `class_weight='balanced'` in model objective.

---

## Evaluation & Benchmarks

### 1. Temporal Hold-Forward Validation (Holdout: Semester 7)
Evaluated on 1,200 unseen semester 7 students after training on semesters 1–6:

| Model / Baseline | Recall | Precision | F1 Score | PR-AUC | ROC-AUC | Balanced Acc |
|---|---|---|---|---|---|---|
| **Majority Class Baseline** | 0.000 | 0.000 | 0.000 | 0.023 | 0.500 | 0.500 |
| **Prior Backlog Rule Baseline** | 0.000 | 0.000 | 0.000 | 0.023 | 0.491 | 0.491 |
| Logistic Regression | **0.964** | 0.188 | 0.314 | 0.706 | 0.988 | **0.932** |
| Random Forest | 0.464 | **0.684** | 0.553 | 0.627 | **0.989** | 0.730 |
| **HistGradientBoosting (Selected)** | 0.679 | 0.633 | **0.655** | 0.696 | 0.984 | 0.835 |
| XGBoost | 0.607 | 0.630 | 0.618 | 0.688 | 0.981 | 0.799 |

### 2. 5-Fold GroupKFold Cross-Validation (Grouped by Student ID)
| Metric | HistGradientBoosting Mean | Standard Deviation |
|---|---|---|
| **F1 Score** | **0.583** | $\pm 0.041$ |
| **Recall** | **0.555** | $\pm 0.048$ |
| **Precision** | **0.628** | $\pm 0.052$ |
| **ROC-AUC** | **0.959** | $\pm 0.012$ |
| **PR-AUC** | **0.636** | $\pm 0.038$ |
| **Balanced Accuracy**| **0.772** | $\pm 0.027$ |

---

## Decision Threshold
- **Selected Threshold**: `0.330`
- **Rationale**: An unadjusted 0.50 threshold suffers from lower recall on high-imbalance (2.7%) academic risk datasets. A tuned threshold of 0.330 elevates recall to 58.3% while maintaining high precision (59.2%), maximizing early-intervention coverage without alarming students with excessive false positives.

---

## Anti-Leakage & Governance
- **Strict Leakage Gate**: Verified 0 presence of forbidden current-semester end-term grades, SGPA, backlog counts, credits earned, or future semester columns.
- **Fail-Closed Design**: Any unauthorized target-correlated columns in the inference pipeline raise a fatal `ValueError`.
- **API Guard**: Implemented in `/predict/m3v3/{student_id}` with strict role-based access control (RBAC).
- **Communication Guard**: All predictions explicitly carry honest advisory notes: *"End-term risk estimate based on mid-semester performance. This is a model estimate, not a certainty."*
