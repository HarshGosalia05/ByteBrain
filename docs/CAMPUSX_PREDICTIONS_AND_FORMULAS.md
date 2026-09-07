# CampusX — Predictions, Models, Formulas & Derived Intelligence

## 1. Purpose

This document provides a complete, source-code-verified reference for every prediction, calculated metric, formula, rule-based insight, ML model, and GenAI explanation currently implemented in CampusX. It traces every derived value from raw database fields through processing, feature engineering, models/formulas, output, and UI display.

No application logic was modified; only this documentation file was created.

---

## 2. System Intelligence Overview

CampusX implements four categories of intelligence:

| Category | Description | Examples |
|---|---|---|
| **ML Predictions** | Trained scikit-learn models loaded from joblib artifacts | M1 V2 subject marks, M2 V2 next-semester SGPA, M3 V2 at-risk |
| **Rule-Based Formulas** | Deterministic, threshold-based calculations with no ML | Academic Health Score, Career Readiness Score (MD-06), marks derivation |
| **Analytics** | Descriptive statistics computed from database queries | Semester averages, attendance distributions, department overviews |
| **GenAI Explanations** | LLM-generated narrative explanations of existing structured predictions | Prediction explanations, chatbot responses |

### Model Generations

| Generation | Location | Data Source | Status |
|---|---|---|---|
| V1 (legacy) | `ml/src/` | 80 synthetic students | REBUILD |
| V2 (production) | `ml/v2/` | 1,200 real CSE 6A students | ACTIVE |
| V3 (experimental) | `ml/v3/` | Local CSV (8,000 rows) | EXPERIMENTAL |
| M4 | `ml/src/m4/` + `ml/m4_career_readiness.py` | 4 database tables | ACTIVE (rule-based) |

---

## 3. Complete Prediction Inventory

| ID | Feature | Type | Purpose | Backend Location | API Endpoint | Status |
|---|---|---|---|---|---|---|
| M1 V1 | Subject Performance | ML Regression | Predict end_sem_marks | `ml/src/` | `/predict/m1/{id}` | REBUILD |
| M1 V2 | Subject Performance | ML Regression | Predict end_sem_marks | `ml/v2/m1_subject_prediction/` | `/predict/m1v2/{id}` | ACTIVE |
| M1 V3 | Subject Performance | ML Regression | Predict end_sem_marks (synthetic) | `ml/v3/m1_subject_prediction/` | `/predict/m1v3/{id}` | EXPERIMENTAL |
| M2 V1 | Next-Semester Performance | ML Regression | Predict next SGPA + percentage | `ml/src/` | `/predict/m2/{id}` | REBUILD |
| M2 V2 | Next-Semester Performance | ML Regression | Predict next SGPA + percentage | `ml/v2/m2_next_semester_prediction/` | `/predict/m2v2/{id}` | ACTIVE |
| M3 V1 | Academic Risk | ML Classification | Predict is_at_risk_next_sem | `ml/src/` | `/predict/m3/{id}` | BLOCKED |
| M3 V2 | Academic Risk | ML Classification | Predict is_at_risk_next_sem | `ml/v2/m3_at_risk_prediction/` | `/predict/m3v2/{id}` | ACTIVE |
| M4 | Career Readiness | Rule-Based | Score 0-100 career readiness | `ml/src/m4/engine.py` | `/predict/m4/{id}` | ACTIVE |
| MD-03 | Performance Analytics | Rule-Based | Trends, strengths, gaps, benchmarks | `backend/app/services/student_analytics_rules.py` | Student analytics | ACTIVE |
| MD-04 | Attendance What-If | Rule-Based | Attendance projection simulation | `backend/app/services/student_analytics_rules.py` | Student attendance | ACTIVE |
| MD-05 | Academic Health Score | Rule-Based | Weighted 0-100 health score | `backend/app/services/student_health_rules.py` | Student health | ACTIVE |
| MD-06 | Career Readiness (API) | Rule-Based | Weighted 0-100 career score | `backend/app/services/student_career_rules.py` | Student career | ACTIVE |
| - | Marks Derivation | Formula | total/pct/grade/result from marks | `backend/app/services/faculty_service.py` | Faculty marks entry | ACTIVE |
| - | Attendance Status | Formula | Status/eligibility from attendance % | `backend/app/services/faculty_service.py` | Faculty attendance | ACTIVE |
| - | Notification Rules | Rule-Based | Event-triggered notifications | `backend/app/services/notification_rules.py` | Notifications | ACTIVE |

---

## 4. End-to-End Prediction Pipeline

### M1 V2 — Subject Performance Prediction

```
Raw Database Data
    students.student_id, students.department_name, students.gender
    student_subject_performance.student_id, student_id, subject_id, semester_no,
        internal_marks, mid_sem_marks, end_sem_marks
    student_subject_enrollment.student_id, subject_id, semester_no, credits
    attendance_weekly.student_id, subject_id, semester_no, attendance_percentage
    semester_summary.student_id, semester_no, sgpa, percentage, backlog_count
    student_learning_activity.student_id, subject_id, semester_no, study_hours, ...
    student_lifestyle_survey.student_id, stress_level, ...
        ↓
Data Retrieval: ml/v2/m1_subject_prediction/data/loader.py → SupabaseLoader
    SQL queries filtered by student_id LIKE 'STU6A%' (cohort guard)
        ↓
Preprocessing: ml/v2/m1_subject_prediction/preprocessing/pipeline.py → M1Preprocessor
    Median imputation (fit on train only)
        ↓
Feature Engineering: ml/v2/m1_subject_prediction/features/builder.py → M1FeatureBuilder
    Point-in-time: only data from semester <= current_semester
    Joins: performance + enrollment + attendance + learning_activity + lifestyle + semester_summary
    39 features total (see Section 12)
        ↓
Feature Vector (39 features):
    [internal_marks, mid_sem_marks, pre_endsem_assessment_pct, assignment_score,
     quiz_avg_marks, submission_delay_days, att_total_pct, att_rolling_4w_mean,
     att_velocity_latest, credits, semester_no, activity_volume_total,
     avg_engagement_consistency, avg_assessment_completion_rate,
     avg_late_submission_rate, study_hours_per_week, is_male, stress_ordinal,
     subject_type_Laboratory, subject_type_Project, subject_type_Theory,
     subject_domain_* (one-hot), prior_avg_sgpa, sgpa_drift_latest,
     prior_backlog_cumulative, prior_avg_attendance, prior_n_sems, ...]
        ↓
ML Model: Ridge Regression (selected from CV comparison of ridge, random_forest, hist_gbm, xgboost)
    Artifact: ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib
        ↓
Prediction: end_sem_marks (continuous, not clipped — output may exceed 0-70)
        ↓
Post-processing: M1V2Predictor.predict() adds grade_band mapping:
    percentage = (end_sem_marks / 70) * 100
    grade_band: >=90 "O" | >=80 "A+" | >=70 "A" | >=60 "B+" | >=50 "B" | >=40 "C" | <40 "F"
        ↓
API Response: GET /api/v1/predict/m1v2/{student_id}
    Response schema: M1V2PredictionResponse
        ↓
Frontend Display: Student prediction page, ML Intelligence admin dashboard
```

Source:
- `ml/v2/m1_subject_prediction/inference/predictor.py` — `M1V2Predictor.predict()`
- `ml/v2/m1_subject_prediction/features/builder.py` — `M1FeatureBuilder.build_features()`
- `ml/v2/m1_subject_prediction/preprocessing/pipeline.py` — `M1Preprocessor`
- `backend/app/services/m1v2_prediction_service.py` — `M1V2PredictionService.predict()`
- `backend/app/api/v1/predict.py` — `predict_m1_v2()`

### M2 V2 — Next-Semester Performance Prediction

```
Raw Database Data (same tables as M1)
        ↓
Data Retrieval: ml/v2/m2_next_semester_prediction/data/loader.py → SupabaseLoader
        ↓
Feature Engineering: ml/v2/m2_next_semester_prediction/features/builder.py → M2FeatureBuilder
    Temporal contract: Features from completed semester T; target is semester T+1
    Training transitions: T=1→2, 2→3, 3→4, 4→5, 5→6, 6→7
    CRITICAL: Current-T outcomes (SGPA, percentage) ARE legitimate features (T is complete)
    Forbidden: Only T+1 outcomes (next_semester_sgpa, next_semester_percentage, etc.)
    Leakage gate: features/leakage_gate.py — fail-closed automated scan
        ↓
Feature Vector:
    [semester_sgpa, semester_percentage, semester_total_marks, semester_attendance_percentage,
     backlog_count, credits_registered, credits_earned, subjects_registered,
     prior_avg_sgpa, sgpa_drift_latest, rolling_mean_3_sgpa,
     prior_avg_attendance, prior_backlog_cumulative, prior_n_sems,
     department_name_BBA, department_name_CSE, is_male, ...]
        ↓
ML Model: Ridge Regression (selected from CV comparison)
    Artifact: ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib
        ↓
Prediction (dual output):
    next_semester_sgpa (0-10)
    next_semester_percentage (0-100)
        ↓
Post-processing: M2V2Predictor.predict() adds:
    sgpa_band: >=9.0 "Excellent" | >=7.5 "Good" | >=6.0 "Average" | <6.0 "Needs Attention"
    percentage_band: same as M1 grade bands
    No next-semester check: if current semester >= program_duration, returns NO_DATA
        ↓
API Response: GET /api/v1/predict/m2v2/{student_id}
        ↓
Frontend Display: Student prediction page
```

Source:
- `ml/v2/m2_next_semester_prediction/inference/predictor.py` — `M2V2Predictor.predict()`
- `ml/v2/m2_next_semester_prediction/features/builder.py` — `M2FeatureBuilder.build_features()`
- `backend/app/services/m2v2_prediction_service.py` — `M2V2PredictionService.predict()`

### M3 V2 — Academic Risk Prediction

```
Raw Database Data (same tables as M2)
        ↓
Data Retrieval: ml/v2/m3_at_risk_prediction/data/loader.py → SupabaseLoader
        ↓
Feature Engineering: ml/v2/m3_at_risk_prediction/features/builder.py → M3FeatureBuilder
    Same T-only features as M2, plus:
    subj_failed_subjects_count (count of T subjects with FAIL/ATKT result_status)
    Leakage gate: features/leakage_gate.py with M3-specific forbidden list
        ↓
Feature Vector:
    [Same as M2 features + subj_failed_subjects_count]
        ↓
ML Model: Logistic Regression / Random Forest / Hist GBM / XGBoost
    (all with class_weight='balanced' for imbalanced classes ~2.8% positive)
    Artifact: ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib
        ↓
Prediction:
    probability_at_risk = model.predict_proba(X)[0][1]
    threshold: Tuned on group-validation probabilities, maximizing F1 subject to
               recall >= 0.50 and precision >= 0.15
    is_estimated_at_risk = probability_at_risk >= threshold
        ↓
Post-processing: M3V2Predictor.predict() adds:
    risk_level: "high" (probability >= 0.7) | "medium" (probability >= threshold) | "low"
    signals: top contributing features by model importance or
             logistic coefficient × standardized value
        ↓
API Response: GET /api/v1/predict/m3v2/{student_id}
        ↓
Frontend Display: Risk & Early Warning, ML Intelligence dashboard
```

Source:
- `ml/v2/m3_at_risk_prediction/inference/predictor.py` — `M3V2Predictor.predict()`
- `ml/v2/m3_at_risk_prediction/features/builder.py` — `M3FeatureBuilder.build_features()`
- `backend/app/services/m3v2_prediction_service.py` — `M3V2PredictionService.predict()`

### M4 — Career Readiness (Rule-Based, NOT ML)

```
Raw Database Data:
    students: student_id, department_name, current_semester
    semester_summary: semester_no, semester_percentage, sgpa, attendance_percentage,
                      backlog_count, semester_result
    career_preferences: internship_completed, certification_interest,
                        higher_studies_interest, entrepreneurship_interest
    student_lifestyle_survey: daily_study_hours, attendance_commitment,
                              mental_wellbeing, stress_level, average_sleep_hours,
                              physical_activity
        ↓
Data Retrieval: ml/src/prediction_service.py → fetch_m4_raw_data()
        ↓
Feature Validation: ml/src/features.py → prepare_m4_inputs()
    Validates required columns exist in each DataFrame (pass-through, no transform)
        ↓
M4 Scoring Engine: ml/src/m4/engine.py → CareerReadinessEngine.score()
    Pure rule-based scoring (NO ML model is used for prediction)
        ↓
Score Calculation (see Section 15.3 for full formula):
    Final Score = Academic Performance (35) + Growth Trend (10) +
                  Career Preparedness (25) + Lifestyle Discipline (30)
        ↓
Post-processing:
    Level: >=75 "High" | >=50 "Medium" | <50 "Low"
    Positive factors and risk factors strings generated from component scores
        ↓
API Response: GET /api/v1/predict/m4/{student_id}
        ↓
Frontend Display: Career Readiness page, ML Intelligence dashboard
```

Source:
- `ml/src/m4/engine.py` — `CareerReadinessEngine.score()`
- `ml/src/inference.py` — `InferenceService.predict_m4()`
- `ml/src/prediction_service.py` — `PredictionService.predict_m4_for_student()`
- `backend/app/api/v1/predict.py` — `predict_m4()`

---

## 5. M1 — Subject Performance Prediction

### M1 V2 (Production)

**What is being predicted:** End-semester marks (`end_sem_marks`) for a specific subject enrollment of a student in a specific semester.

**Target variable:** `end_sem_marks` (continuous, typically 0-70 on the marks scale)

**Training data:** 1,200 CSE 6A students across semesters 1-8. Temporal split: train on semesters 1-6, holdout semester 7.

**Model:** Ridge Regression (selected because it had lowest mean MAE in 5-fold GroupKFold CV by student_id, plus temporal hold-forward validation).

**CV MAE:** 6.319 ± stdev. Temporal MAE (sem 7): 6.302. R²=0.423.

**Artifact:** `ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib`

**39 Features:**

| Feature | Source Table | Source Column | Transformation |
|---|---|---|---|
| internal_marks | student_subject_performance | internal_marks | none (0-20) |
| mid_sem_marks | student_subject_performance | mid_sem_marks | none (0-50) |
| pre_endsem_assessment_pct | student_subject_performance | computed | (internal_marks + mid_sem_marks) / (20+50) * 100 |
| assignment_score | student_learning_activity | assignment_score | aggregation |
| quiz_avg_marks | student_learning_activity | quiz_avg_marks | aggregation |
| submission_delay_days | student_learning_activity | submission_delay_days | sum |
| att_total_pct | attendance_weekly | attendance_percentage | mean over semester |
| att_rolling_4w_mean | attendance_weekly | attendance_percentage | rolling 4-week mean |
| att_velocity_latest | attendance_weekly | attendance_percentage | trend slope |
| credits | student_subject_enrollment | credits | none |
| semester_no | semester_summary | semester_no | none |
| activity_volume_total | student_learning_activity | various | count of activities |
| avg_engagement_consistency | student_learning_activity | various | std-dev based |
| avg_assessment_completion_rate | student_learning_activity | various | ratio |
| avg_late_submission_rate | student_learning_activity | various | ratio |
| study_hours_per_week | student_lifestyle_survey | daily_study_hours | * 7 |
| is_male | students | gender | binary (1 if Male, 0 if Female) |
| stress_ordinal | student_lifestyle_survey | stress_level | ordinal encoding (Low=0, Medium=1, High=2) |
| subject_type_* | subjects | subject_type | one-hot (Theory, Laboratory, Project, Internship) |
| subject_domain_* | subjects | subject_name | domain keyword matching, one-hot |
| prior_avg_sgpa | semester_summary | sgpa | mean of all prior semesters |
| sgpa_drift_latest | semester_summary | sgpa | last - second-to-last semester SGPA |
| prior_backlog_cumulative | semester_summary | backlog_count | cumulative sum of prior backlogs |
| prior_avg_attendance | attendance_weekly | attendance_percentage | mean of all prior semesters |
| prior_n_sems | semester_summary | semester_no | count of prior completed semesters |

**Missing value handling:** Median imputation (fit on training data only, applied at inference).

**Grade band derivation (post-prediction):**
- `percentage = (predicted_marks / 70) * 100`
- `>=90%` → "O" | `>=80%` → "A+" | `>=70%` → "A" | `>=60%` → "B+" | `>=50%` → "B" | `>=40%` → "C" | `<40%` → "F"

### M1 V1 (Legacy)

Same purpose. Uses `hist_gbm` (histogram-based gradient boosting). Artifact: `ml/artifacts/models/m1_subject_endmarks.joblib`. Status: REBUILD — metrics inflated by near-stationary synthetic data.

### M1 V3 (Experimental)

Trained on local CSV (8,000 rows, 80 students). Uses 8 features only. Algorithm: `linear_regression`. CV MAE: 4.6843. Artifact: `ml/v3/m1_subject_prediction/artifacts/m1_synthetic_v1.joblib`. Status: EXPERIMENTAL — limited production compatibility.

---

## 6. M2 — Next-Semester Performance Prediction

### M2 V2 (Production)

**What is being predicted:** A student's SGPA and percentage for the next semester (T+1), given their completed semester T data.

**Target variables:**
- `next_semester_sgpa` (continuous, 0-10)
- `next_semester_percentage` (continuous, 0-100)

**Temporal contract:** Features come from completed semester T. Target is semester T+1. Training transitions: T=1→2, 2→3, 3→4, 4→5, 5→6, 6→7 (excludes T=7→8 internship).

**Model:** Ridge Regression (selected from CV comparison).

**Artifact:** `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib`

**Key features:** semester_sgpa, semester_percentage, semester_total_marks, semester_attendance_percentage, backlog_count, credits_registered, credits_earned, subjects_registered, prior_avg_sgpa, sgpa_drift_latest, rolling_mean_3_sgpa, prior_avg_attendance, prior_backlog_cumulative, prior_n_sems, department_name_BBA, department_name_CSE, is_male, subject-level aggregates, attendance aggregates, learning activity aggregates, lifestyle, gender.

**CRITICAL DESIGN:** Current-T outcomes (SGPA, percentage) ARE legitimate features because T is complete. Only T+1 outcomes are forbidden.

**Leakage gate:** `ml/v2/m2_next_semester_prediction/features/leakage_gate.py` — fail-closed automated scan for forbidden columns.

**Inference behavior:**
- Determines observation semester T from most recent COMPLETED semester (sgpa > 0 AND percentage > 0).
- If current semester >= program_duration (8), returns NO_DATA.
- Output includes sgpa_band and percentage_band for display.

### M2 V1 (Legacy)

Same purpose. Uses `hist_gbm`. Artifact: `ml/artifacts/models/m2_next_semester_performance.joblib`. Status: REBUILD.

---

## 7. M3 — Academic Risk Prediction

### M3 V2 (Production)

**Definition of academic risk:** A student is "at risk" for the next semester if they will FAIL/ATKT or have backlog_count > 0 in semester T+1.

**Target variable:** `is_at_risk_next_sem` (binary: 1 = at risk, 0 = not at risk)

**Class distribution:** ~2.8% positive (very imbalanced).

**Model:** Logistic Regression / Random Forest / Hist GBM / XGBoost (all with `class_weight='balanced'`).

**Threshold:** Tuned on GROUP-VALIDATION probabilities (NOT the holdout), maximizing F1 subject to recall >= 0.50 and precision >= 0.15.

**Artifact:** `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib`

**Features:** Same as M2 plus `subj_failed_subjects_count` (count of semester T subjects with FAIL/ATKT result_status).

**Output:**
- `probability_at_risk`: `model.predict_proba(X)[0][1]`
- `threshold`: Optimized threshold from validation
- `is_estimated_at_risk`: `probability_at_risk >= threshold`
- `risk_level`: "high" (probability >= 0.7) | "medium" (probability >= threshold) | "low"
- `signals`: Top contributing features by model importance or logistic coefficient × standardized value

**Leakage gate:** `ml/v2/m3_at_risk_prediction/features/leakage_gate.py` — M3-specific forbidden list.

### M3 V1 (Legacy)

Uses `hist_gbm`. Artifact: `ml/artifacts/models/m3_next_semester_at_risk.joblib`. Status: BLOCKED from production (validation gate FAIL / insufficient positive-class coverage).

---

## 8. M4 — Career Readiness

### M4 (Rule-Based Engine)

**Classification: DETERMINISTIC RULE-BASED — NOT ML.** Despite having ML training code (`ml/src/m4/train_m4.py`), the production prediction uses the `CareerReadinessEngine` class (`ml/src/m4/engine.py`) which is a pure rule-based scoring engine.

**Engine location:** `ml/src/m4/engine.py` — `CareerReadinessEngine`

**Weights (configurable):**

| Component | Max Points | Weight |
|---|---|---|
| Academic Performance | 35 | 0.35 |
| Growth Trend | 10 | 0.10 |
| Career Preparedness | 25 | 0.25 |
| Lifestyle & Discipline | 30 | 0.30 |
| **Total** | **100** | **1.00** |

**Component Breakdown:**

#### Academic Performance (35 points)
```
score = percentage_score + attendance_score + backlog_score

percentage_score = scale(avg_semester_percentage, 40, 95, 20)
    Where scale(x, lo, hi, max) = clip((x - lo) / (hi - lo), 0, 1) * max

attendance_score = scale(avg_semester_attendance, 50, 95, 10)

backlog_score:
    0 backlogs → 5
    <=2 backlogs → 3
    <=4 backlogs → 1
    >4 backlogs → 0
```

#### Growth Trend (10 points)
```
slope = np.polyfit(semesters, percentages, 1)[0]
    (linear regression slope of semester percentage over time)
score = clip((slope + 2) / 4, 0, 1) * 10
    Maps slope range [-2, +2] to [0, 10]
    If no trend data → score = 5.0 (neutral)
```

#### Career Preparedness (25 points)
```
internship_score:
    "Yes" → 15
    "No" → 0

certification_score:
    "Yes" → 5
    "No" → 0

forward_planning_score:
    (higher_studies_interest == "Yes" OR entrepreneurship_interest == "Yes") → 5
    Otherwise → 0

score = internship_score + certification_score + forward_planning_score
```

#### Lifestyle & Discipline (30 points)
```
study_hours_score = scale(daily_study_hours, 0, 12, 10)

attendance_commitment_score:
    "Poor" → 2 | "Average" → 5 | "Good" → 7 | "Very Good" → 9 | "Excellent" → 10
    (then scale to 10 points)

wellbeing_score:
    "Poor" → 0 | "Average" → 2.5 | "Good" → 4 | "Excellent" → 5
    (then scale to 5 points)

sleep_score:
    7-9 hours → 3 | 6-7 or 9-10 → 2 | 5-6 or 10-11 → 1 | else → 0

activity_score:
    "Never" → 0 | "Rare" → 0.7 | "Moderate" → 1.4 | "Regular" → 2.0

score = study_hours_score + attendance_commitment_score + wellbeing_score +
        sleep_score + activity_score
```

**Level thresholds:** `>=75 "High"` | `>=50 "Medium"` | `<50 "Low"`

**Positive/Risk factors:** Generated from component scores (e.g., high academic score → positive factor; high backlogs → risk factor).

---

## 9. M5 / Other Deterministic Intelligence

### No M5 module exists. The M4 engine at `ml/src/m4/engine.py` is the only deterministic intelligence module beyond the MD-* modules below.

### ML-Based M4 (Legacy, Not Used in Production)

There is an ML-based M4 implementation at `ml/src/m4/train_m4.py` that trains a classifier on `placement_readiness_level`. This is **NOT** the production M4 — the production M4 uses the rule-based `CareerReadinessEngine`. The ML version has:
- Target: `placement_readiness_level` (categorical)
- Algorithms: logistic_regression, random_forest, hist_gbm
- Features: preferred_domain, dream_job_role, preferred_industry, preferred_work_mode, certification_interest, higher_studies_interest, entrepreneurship_interest, internship_completed, avg_prior_percentage, avg_prior_sgpa, avg_prior_attendance, total_prior_backlogs
- Status: Not used in production prediction endpoints

---

## 10. Rule-Based Insights

### MD-03: Student Performance Analytics

Source: `backend/app/services/student_analytics_rules.py`

#### 1. Performance Trends (`compute_trends`)
- **Input:** semester_summary rows (sorted by semester)
- **Logic:** For each metric (sgpa, percentage, attendance), computes movement between last two completed semesters
- **Direction:** delta > tolerance → "up" | delta < -tolerance → "down" | else → "flat"
- **Tolerance:** `settings.STUDENT_TREND_STABLE_TOLERANCE` (0.1)
- **Overall direction:** Compares first and last semester SGPA

#### 2. Subject Strengths (`compute_strengths`)
- **Classification rule:**
  - `percentage >= 75` → "Strong"
  - `percentage >= 60` → "Good"
  - `percentage >= 45` → "Needs Attention"
  - `percentage < 45` → "Critical"
- **Output:** Only subjects classified as "Strong" or "Good"

#### 3. Needs Attention (`compute_needs_attention`)
- **Priority rules (lowest number = highest priority):**
  1. `result_status == "fail"` → "Failed result" (priority 1)
  2. `percentage < 45` → "Very low percentage" (priority 2)
  3. `percentage < 60` → "Needs attention" (priority 3)
  4. Performance declined across attempts → "Declining" (priority 4)
  5. `percentage is None` → "Final result pending" (priority 5)

#### 4. Learning Gaps (`compute_learning_gaps`)
- **Assessment progression gap:** If `internal% - mid% >= 20` OR `mid% - end% >= 20` → gap detected
- **Repeated low performance:** All attempts below 45%
- **Repeated weakness:** All attempts below 60%

#### 5. Class Benchmark (`compute_benchmark`)
- **Logic:** Compares student percentage to class average for same subject/semester
- **Minimum cohort size:** 5 students (from `settings.STUDENT_CLASS_BENCHMARK_MIN_COHORT`)

#### 6. Attempt History (`compute_attempt_history`)
- Groups performance rows by subject, tracks all attempts
- Computes improvement = last_attempt_percentage - first_attempt_percentage

### MD-04: Attendance What-If Simulation

Source: `backend/app/services/student_analytics_rules.py` — `compute_attendance_what_if()`

```
current_attendance = attended_classes / total_classes * 100
new_total = total_classes + hypothetical_present + hypothetical_absent
new_attended = attended_classes + hypothetical_present
resulting_attendance = new_attended / new_total * 100

classes_to_reach_target:
    if current < target:
        ceil((target_fraction * total_classes - attended_classes) / (1 - target_fraction))
    else: 0

classes_to_skip_below_target:
    if current >= target:
        floor(attended_classes / target_fraction - total_classes)
    else: 0
```

### MD-05: Academic Health Score

Source: `backend/app/services/student_health_rules.py` — `compute_health_score()`

```
Components (weighted average, renormalized over available):
    attendance  (weight 0.30): current attendance %
    performance (weight 0.35): mean of completed subject percentages
    progress    (weight 0.20): latest semester_percentage or sgpa * 10
    consistency (weight 0.15): 100 - (pstdev(sgpas) * 10)

Minimum components for score: 2 (settings.HEALTH_AVAILABLE_COMPONENT_MIN)

Bands:
    >= 80 → "Excellent"
    >= 65 → "Good"
    >= 50 → "Watch"
    < 50  → "Needs Attention"
```

**Priority ranking ("What should I focus on?"):**

| Priority | Signal | Condition |
|---|---|---|
| 1 | attendance | attendance < 75% target |
| 2 | weak_performance | subject percentage < performance band |
| 3 | declining_trend | latest SGPA/percentage trend is declining |
| 4 | pending_result | current-semester final result still pending |
| 5 | backlog | unresolved backlogs from completed semesters |
| 6 | eligibility_issue | not eligible for examination |
| 7 | goal_gap | active goal target not yet reached |

### MD-06: Career Readiness Score (API)

Source: `backend/app/services/student_career_rules.py` — `compute_career_readiness()`

```
Components (weighted average, renormalized over available):
    academic    (weight 0.30): mean of completed subject percentages
    consistency (weight 0.15): 100 - (pstdev(sgpas) * 10)
    alignment   (weight 0.20): % of completed subjects relevant to preferred domain
    attendance  (weight 0.15): current attendance %
    internship  (weight 0.10): "Yes"→100, "No"→0
    readiness   (weight 0.10): "Low"→25, "Medium"→50, "High"→75, "Excellent"→100

Minimum components for score: 2

Bands:
    >= 80 → "Strong"
    >= 60 → "Good"
    >= 40 → "Developing"
    < 40  → "Needs Attention"
```

**Domain alignment (`compute_domain_alignment`):**
- A subject is "domain-relevant" if its name contains any keyword from `DOMAIN_SUBJECT_KEYWORDS` for the student's preferred domain
- Alignment = aligned_subjects / total_completed_subjects * 100
- Keywords per domain defined in `student_career_rules.py` (e.g., "Data Science" → ["data", "statistics", "analytics", "machine learning", ...])

### Notification Rules

Source: `backend/app/services/notification_rules.py`

Generates event-triggered notifications for students based on:
- Low attendance (below 75%)
- Failed results
- Backlog accumulation
- Risk predictions (M3 at-risk)
- Performance drops

---

## 11. Analytics Calculations

Source: `backend/app/services/analytics_service.py`, `backend/app/repositories/analytics_repo.py`

### Student Analytics
- **Academic Profile:** Aggregated from students + semester_summary tables
- **Semester History:** Per-semester SGPA, percentage, attendance, backlog
- **Attendance Summary:** Aggregated attendance percentage per subject/semester
- **Backlog Summary:** Total backlogs across semesters

### Subject Analytics
- **Performance Summary:** Average marks, pass rate, grade distribution per subject
- **Attendance Summary:** Average attendance per subject
- **Underperformers:** Students below a threshold (default 40%)

### Department Analytics
- **Overview:** Student counts, average SGPA, pass rates by department
- **Performance Distribution:** Histogram buckets of semester percentages
- **Attendance Distribution:** Histogram buckets of attendance percentages
- **Backlog Distribution:** Count of students by backlog ranges

### At-Risk Analytics
- **At-Risk Students:** Students with attendance < 75%, or SGPA < threshold, or backlogs > 0
- **Below Attendance Threshold:** Students with attendance < configurable threshold
- **Subjects Needing Attention:** Subjects with high failure rates or low average performance

### Faculty Analytics (in `faculty_service.py`)
- **Performance Summary/Distributions/Trends:** Aggregated marks analytics
- **Attendance Summary/Distributions/Trends:** Aggregated attendance analytics
- **Workload Summary/Capacity/Forecast:** Teaching workload calculations
- **Attendance Health Score:** Band classification based on attendance percentage
- **Workload Health Score:** Weighted score of utilization, balance, coverage, efficiency

### Marks Derivation (in `faculty_service.py`)

Source: `backend/app/services/faculty_service.py` — `derive_marks_fields()`

```
total_marks = internal_marks + mid_sem_marks + end_sem_marks
percentage = total_marks / 140 * 100

Grade bands:
    >= 90% → "O" (10)
    >= 80% → "A+" (9)
    >= 70% → "A" (8)
    >= 60% → "B+" (7)
    >= 50% → "B" (6)
    >= 40% → "C" (5)
    < 40%  → "F" (0)

Result status:
    Pass if percentage >= 40% AND end_sem_marks >= 18
    Fail otherwise

Performance category:
    >= 90% → "Top"
    >= 80% → "Above Average"
    >= 60% → "Average"
    >= 40% → "Below Average"
    < 40%  → "Low Performer"

Remarks:
    >= 90% → "Excellent performance"
    >= 75% → "Good performance"
    >= 60% → "Satisfactory performance"
    >= 40% → "Needs improvement"
    < 40%  → "At risk - improvement required"
```

### Attendance Status Derivation

Source: `backend/app/services/faculty_service.py` — `attendance_aggregate_fields()`

```
if percentage < 60% → "Critical"
elif percentage < 75% → "Low"
elif percentage < 80% → "Average"
elif percentage < 90% → "Good"
else → "Excellent"

eligibility: percentage >= 75% → "Eligible" | else → "Not Eligible"
shortage_flag: percentage < 75% → "Yes" | else → "No"
```

---

## 12. Feature Engineering

### M1 V2 Features (39 total)

| # | Feature | Source Table | Source Column | Transformation | Final Meaning |
|---|---|---|---|---|---|
| 1 | internal_marks | student_subject_performance | internal_marks | none | Internal assessment marks (0-20) |
| 2 | mid_sem_marks | student_subject_performance | mid_sem_marks | none | Mid-semester marks (0-50) |
| 3 | pre_endsem_assessment_pct | computed | (internal+mid)/(20+50)*100 | percentage | Pre-endsem assessment completion |
| 4 | assignment_score | student_learning_activity | assignment_score | aggregation | Assignment scores |
| 5 | quiz_avg_marks | student_learning_activity | quiz_avg_marks | aggregation | Average quiz marks |
| 6 | submission_delay_days | student_learning_activity | submission_delay_days | sum | Total late submission days |
| 7 | att_total_pct | attendance_weekly | attendance_percentage | mean | Overall attendance % for semester |
| 8 | att_rolling_4w_mean | attendance_weekly | attendance_percentage | rolling mean | 4-week rolling attendance |
| 9 | att_velocity_latest | attendance_weekly | attendance_percentage | slope | Attendance trend direction |
| 10 | credits | student_subject_enrollment | credits | none | Subject credits |
| 11 | semester_no | semester_summary | semester_no | none | Current semester number |
| 12 | activity_volume_total | student_learning_activity | various | count | Total learning activities |
| 13 | avg_engagement_consistency | student_learning_activity | various | std-dev | Engagement regularity |
| 14 | avg_assessment_completion_rate | student_learning_activity | various | ratio | Assessment completion rate |
| 15 | avg_late_submission_rate | student_learning_activity | various | ratio | Late submission rate |
| 16 | study_hours_per_week | student_lifestyle_survey | daily_study_hours | * 7 | Weekly study hours |
| 17 | is_male | students | gender | binary | Gender indicator |
| 18 | stress_ordinal | student_lifestyle_survey | stress_level | ordinal | Stress level (0/1/2) |
| 19-22 | subject_type_* | subjects | subject_type | one-hot | Theory/Laboratory/Project/Internship |
| 23-? | subject_domain_* | subjects | subject_name | keyword match + one-hot | Domain classification |
| ? | prior_avg_sgpa | semester_summary | sgpa | mean(prior sems) | Historical academic performance |
| ? | sgpa_drift_latest | semester_summary | sgpa | last - second-to-last | SGPA change direction |
| ? | prior_backlog_cumulative | semester_summary | backlog_count | cumsum | Total prior backlogs |
| ? | prior_avg_attendance | attendance_weekly | attendance_percentage | mean(prior sems) | Historical attendance |
| ? | prior_n_sems | semester_summary | semester_no | count(prior) | Semesters of history |

### Missing Value Handling
- **M1 V2:** Median imputation (fit on training data only, applied at inference time)
- **M2 V2 / M3 V2:** Same pattern — median imputation from training

### Preprocessing
- **M1 V2:** `M1Preprocessor` — median imputation only, no scaling needed for Ridge
- **M2 V2 / M3 V2:** Median imputation + standard scaling for some algorithms

---

## 13. ML Models

### Model Registry

Source: `ml/src/registry.py`

| Model ID | Algorithm | Artifact Path | Status |
|---|---|---|---|
| m1 (V1) | hist_gbm | `ml/artifacts/models/m1_subject_endmarks.joblib` | REBUILD |
| m2 (V1) | hist_gbm | `ml/artifacts/models/m2_next_semester_performance.joblib` | REBUILD |
| m3 (V1) | hist_gbm | `ml/artifacts/models/m3_next_semester_at_risk.joblib` | BLOCKED |
| m1 (V2) | ridge | `ml/v2/m1_subject_prediction/artifacts/models/m1_v2_subject_endmarks.joblib` | ACTIVE |
| m2 (V2) | ridge | `ml/v2/m2_next_semester_prediction/artifacts/models/m2_v2_next_semester.joblib` | ACTIVE |
| m3 (V2) | TBD | `ml/v2/m3_at_risk_prediction/artifacts/models/m3_v2_at_risk.joblib` | ACTIVE |
| m4 | rule-based engine | `ml/artifacts/models/m4_career_readiness.joblib` | ACTIVE |

### M1 V2 Ridge Regression

- **Type:** Regression
- **Target:** end_sem_marks (continuous)
- **Algorithm:** `sklearn.linear_model.Ridge`
- **CV Method:** GroupKFold(5) by student_id + temporal hold-forward
- **CV MAE:** 6.319 ± stdev
- **Temporal MAE:** 6.302 (semester 7 holdout)
- **R²:** 0.423
- **Baselines beaten:** mean predictor (8.413 MAE) by 25%, prior-semester-mean (7.509) by 16%

### M2 V2 Ridge Regression

- **Type:** Regression (dual target)
- **Target:** next_semester_sgpa, next_semester_percentage
- **Algorithm:** `sklearn.linear_model.Ridge`
- **CV Method:** GroupKFold(5) + temporal hold-forward
- **Baselines:** mean predictor, carry-forward (repeat current T's value)

### M3 V2 Classification

- **Type:** Binary classification
- **Target:** is_at_risk_next_sem (0/1)
- **Class distribution:** ~2.8% positive
- **Algorithm:** Logistic Regression / Random Forest / Hist GBM / XGBoost (with `class_weight='balanced'`)
- **Threshold:** Tuned to maximize F1 subject to recall >= 0.50 and precision >= 0.15
- **No synthetic oversampling:** SMOTE/ADASYN are never used

### M4 Rule-Based Engine

- **Type:** Deterministic scoring (NOT ML)
- **Algorithm:** Custom weighted scoring engine
- **Artifact:** Serialized via joblib for consistent loading
- **Determinism:** Identical inputs → identical outputs (verified by tests)

### Inference Contract (V1 Unified)

Source: `ml/src/features/v1_inference_contract.py`

The V1 inference contract wraps M1/M2/M3 behind a readiness-aware boundary:
- `MODEL_READINESS`: m1=READY, m2=READY, m3=READY (updated from BLOCKED)
- `predict_m1()`, `predict_m2()`, `predict_m3()` — single-row offline inference
- Input validation, feature contract enforcement, forbidden feature rejection
- Deterministic results (identical input → identical output)

### Probability / Confidence Calculations

- **M1 V2:** No probability — continuous regression. Output is point prediction.
- **M2 V2:** No probability — continuous regression. Dual output (SGPA, percentage).
- **M3 V2:** `probability_at_risk = model.predict_proba(X)[0][1]` — probability of positive class.
  - Risk level: probability >= 0.7 → "high" | probability >= threshold → "medium" | else → "low"
  - Signals: top contributing features by model importance or logistic coefficient × standardized value
- **M4:** No probability — deterministic score. Level: >=75 "High" | >=50 "Medium" | <50 "Low"

---

## 14. Database → Feature Mapping

### Core Tables

| Table | Key Columns | Used By |
|---|---|---|
| students | student_id, enrollment_no, first_name, last_name, gender, department_name, current_semester, admission_year | M1/M2/M3/M4, analytics |
| semester_summary | student_id, semester_no, sgpa, percentage, total_marks, attendance_percentage, backlog_count, semester_result | M1/M2/M3/M4, analytics |
| student_subject_performance | student_id, subject_id, semester_no, internal_marks, mid_sem_marks, end_sem_marks, attempt_number, result_status, grade, grade_point, percentage | M1, analytics |
| student_subject_enrollment | student_id, subject_id, semester_no, credits | M1, analytics |
| attendance_weekly | student_id, subject_id, semester_no, attendance_percentage, total_classes, attended_classes | M1/M2/M3, analytics |
| student_learning_activity | student_id, subject_id, semester_no, study_hours, assignment_score, quiz_avg_marks, submission_delay_days | M1/M2/M3 |
| student_lifestyle_survey | student_id, daily_study_hours, attendance_commitment, mental_wellbeing, stress_level, average_sleep_hours, physical_activity | M1/M2/M3/M4 |
| career_preferences | student_id, preferred_domain, internship_completed, certification_interest, higher_studies_interest, entrepreneurship_interest, placement_readiness_level | M4 |
| subjects | subject_id, subject_name, subject_type, credits | M1, analytics |
| departments | department_code, department_name | analytics |

### Column → Calculation Mapping

| Database Column | Used By | Calculation |
|---|---|---|
| students.cgpa | analytics | Database-derived (no formula) |
| students.department_name | M1/M2/M3, M4 | One-hot encoding |
| students.gender | M1/M2/M3 | Binary encoding (is_male) |
| semester_summary.sgpa | M1 (prior_avg_sgpa, sgpa_drift), M2/M3 (feature), M4 (health consistency) | Aggregation over prior semesters |
| semester_summary.percentage | M1/M2/M3 (feature), M4 (academic component) | Database-derived |
| semester_summary.backlog_count | M1 (prior_backlog_cumulative), M2/M3 (feature), M4 (backlog score) | Cumulative sum |
| semester_summary.attendance_percentage | M1/M2/M3 (prior_avg_attendance), M4 (attendance component) | Mean over prior semesters |
| student_subject_performance.internal_marks | M1 (direct feature), analytics | Database-derived (0-20) |
| student_subject_performance.mid_sem_marks | M1 (direct feature), analytics | Database-derived (0-50) |
| student_subject_performance.end_sem_marks | M1 (target), analytics | Database-derived (0-70) |
| attendance_weekly.attendance_percentage | M1 (att_total_pct, att_rolling, att_velocity), M2/M3 | mean, rolling mean, slope |
| student_learning_activity.* | M1/M2/M3 | Various aggregations |
| career_preferences.internship_completed | M4 (career score) | Binary: "Yes"→100, "No"→0 |
| career_preferences.placement_readiness_level | M4 (MD-06 career score) | Ordinal: Low→25, Medium→50, High→75, Excellent→100 |
| student_lifestyle_survey.* | M1/M2/M3/M4 | Ordinal mapping or direct use |

---

## 15. Formulas

### 15.1 Marks Derivation

Source: `backend/app/services/faculty_service.py` — `derive_marks_fields()`

```
total_marks = internal_marks + mid_sem_marks + end_sem_marks
percentage = total_marks / 140 × 100
grade = lookup(percentage, MARKS_GRADE_BANDS)
result_status = Pass if (percentage ≥ 40 AND end_sem_marks ≥ 18) else Fail
```

**Example:**
- internal_marks = 15, mid_sem_marks = 35, end_sem_marks = 45
- total_marks = 15 + 35 + 45 = 95
- percentage = 95 / 140 × 100 = 67.86%
- grade = "B+" (≥ 60%)
- result_status = "Pass" (67.86% ≥ 40% AND 45 ≥ 18)

### 15.2 Attendance Status

Source: `backend/app/services/faculty_service.py` — `attendance_aggregate_fields()`

```
if percentage < 60%: status = "Critical"
elif percentage < 75%: status = "Low"
elif percentage < 80%: status = "Average"
elif percentage < 90%: status = "Good"
else: status = "Excellent"

eligibility = "Eligible" if percentage ≥ 75% else "Not Eligible"
shortage_flag = "Yes" if percentage < 75% else "No"
```

**Example:**
- percentage = 72%
- status = "Low" (60% ≤ 72% < 75%)
- eligibility = "Not Eligible" (72% < 75%)
- shortage_flag = "Yes"

### 15.3 M4 Career Readiness Score (Rule-Based Engine)

Source: `ml/src/m4/engine.py` — `CareerReadinessEngine`

```
Final Score = Academic Performance + Growth Trend + Career Preparedness + Lifestyle & Discipline
```

**Detailed formulas:**

```
scale(x, lo, hi, max_points) = clip((x - lo) / (hi - lo), 0, 1) × max_points

Academic Performance (35 pts):
  pct_score = scale(avg_semester_percentage, 40, 95, 20)
  att_score = scale(avg_semester_attendance, 50, 95, 10)
  backlog_score = 5 if backlogs==0, 3 if ≤2, 1 if ≤4, 0 if >4
  academic = pct_score + att_score + backlog_score

Growth Trend (10 pts):
  slope = polyfit(semesters, percentages, 1)[0]
  trend = clip((slope + 2) / 4, 0, 1) × 10

Career Preparedness (25 pts):
  internship = 15 if "Yes" else 0
  cert_focus = 5 if "Yes" else 0
  forward_planning = 5 if (higher_studies or entrepreneurship) else 0
  career = internship + cert_focus + forward_planning

Lifestyle & Discipline (30 pts):
  study = scale(daily_study_hours, 0, 12, 10)
  att_commit = attendance_commitment_map[level]  (Poor→2, Average→5, Good→7, Very Good→9, Excellent→10)
  wellbeing = mental_wellbeing_map[level]  (Poor→0, Average→2.5, Good→4, Excellent→5)
  sleep = 3 if 7-9h, 2 if 6-7h or 9-10h, 1 if 5-6h or 10-11h, 0 otherwise
  activity = physical_activity_map[level]  (Never→0, Rare→0.7, Moderate→1.4, Regular→2.0)
  lifestyle = study + att_commit + wellbeing + sleep + activity
```

**Example:**
- avg_semester_percentage = 75, avg_semester_attendance = 82, total_backlogs = 1
- daily_study_hours = 6, stress_level = "Medium", average_sleep_hours = 7.5
- internship_completed = "Yes", certification_interest = "Yes"
- higher_studies_interest = "Yes", entrepreneurship_interest = "No"

```
pct_score = scale(75, 40, 95, 20) = (75-40)/(95-40) × 20 = 35/55 × 20 = 12.73
att_score = scale(82, 50, 95, 10) = (82-50)/(95-50) × 10 = 32/45 × 10 = 7.11
backlog_score = 3 (≤2 backlogs)
academic = 12.73 + 7.11 + 3 = 22.84

slope = 1.5 (improving)
trend = clip((1.5+2)/4, 0, 1) × 10 = 0.875 × 10 = 8.75

internship = 15, cert_focus = 5, forward_planning = 5
career = 15 + 5 + 5 = 25

study = scale(6, 0, 12, 10) = 5.0
att_commit = 7 (Good)
wellbeing = 4 (Good)
sleep = 3 (7.5h is in 7-9 range)
activity = 1.4 (Moderate)
lifestyle = 5.0 + 7 + 4 + 3 + 1.4 = 20.4

Final Score = 22.84 + 8.75 + 25 + 20.4 = 76.99
Level = "High" (≥75)
```

### 15.4 Academic Health Score (MD-05)

Source: `backend/app/services/student_health_rules.py` — `compute_health_score()`

```
Components (weighted average, renormalized over available):
  attendance  (weight 0.30): clamp(attendance_pct, 0, 100)
  performance (weight 0.35): mean(completed_subject_percentages), clamped [0,100]
  progress    (weight 0.20): semester_percentage or sgpa*10, clamped [0,100]
  consistency (weight 0.15): 100 - (pstdev(sgpas) × 10), clamped [0,100]

score = Σ(component_score × weight) / Σ(weight)  (over available components only)
```

**Example:**
- attendance = 82%, completed percentages = [70, 65, 80, 72]
- latest semester_percentage = 75, sgpas = [7.5, 7.8, 7.2]
- All 4 components available

```
attendance_score = 82.0 (weight 0.30)
performance_score = (70+65+80+72)/4 = 71.75 (weight 0.35)
progress_score = 75.0 (weight 0.20)
consistency_score = 100 - (pstdev([7.5, 7.8, 7.2]) × 10) = 100 - (0.2646 × 10) = 97.35 (weight 0.15)

score = (82×0.30 + 71.75×0.35 + 75×0.20 + 97.35×0.15) / (0.30+0.35+0.20+0.15)
      = (24.6 + 25.11 + 15.0 + 14.60) / 1.0
      = 79.31

Band = "Good" (65 ≤ 79.31 < 80)
```

### 15.5 Career Readiness Score (MD-06 API)

Source: `backend/app/services/student_career_rules.py` — `compute_career_readiness()`

```
Components (weighted average, renormalized over available):
  academic    (weight 0.30): mean(completed_subject_percentages), clamped [0,100]
  consistency (weight 0.15): 100 - (pstdev(sgpas) × 10), clamped [0,100]
  alignment   (weight 0.20): domain_alignment_score
  attendance  (weight 0.15): attendance_pct, clamped [0,100]
  internship  (weight 0.10): 100 if "Yes", 0 if "No"
  readiness   (weight 0.10): Low→25, Medium→50, High→75, Excellent→100

score = Σ(component_score × weight) / Σ(weight)  (over available components only)
```

### 15.6 Attendance What-If Projection

Source: `backend/app/services/student_analytics_rules.py` — `compute_attendance_what_if()`

```
current = attended / total × 100
new_total = total + present + absent
new_attended = attended + present
resulting = new_attended / new_total × 100

classes_to_reach_target = ceil((target_frac × total - attended) / (1 - target_frac))
    (only if current < target)
classes_to_skip_below_target = floor(attended / target_frac - total)
    (only if current ≥ target)
```

### 15.7 Assessment Progression Gap Detection

Source: `backend/app/services/student_analytics_rules.py` — `_assessment_progression_gaps()`

```
component_percentage(marks, max_mark) = marks / max_mark × 100

For each consecutive pair (internal→mid, mid→end):
  if previous_pct - current_pct ≥ 20.0:
    gap detected ("Assessment progression gap")
```

### 15.8 Workload Health Score (Faculty)

Source: `backend/app/services/faculty_service.py` — `_health_score()`

```
capacity_score = 100 - abs(utilization - 100)

health = capacity_score × 0.4
       + balance × 0.3
       + coverage × 0.2
       + efficiency × 0.1
```

---

## 16. Thresholds, Weights & Constants

### Marks Constants

| Constant | Value | Meaning | Source |
|---|---:|---|---|
| MARKS_INTERNAL_MAX | 20 | Maximum internal marks | `config.py` |
| MARKS_MID_SEM_MAX | 50 | Maximum mid-semester marks | `config.py` |
| MARKS_END_SEM_MAX | 70 | Maximum end-semester marks | `config.py` |
| MARKS_TOTAL_MAX | 140 | Sum of all max marks | `config.py` |
| MARKS_PASS_PERCENTAGE | 40.0 | Minimum percentage to pass | `config.py` |
| MARKS_END_SEM_PASS_MIN | 18 | Minimum end-sem marks to pass | `config.py` |

### Grade Bands

| Min % | Grade | Grade Point | Source |
|---:|---|---|---|
| 90.0 | O | 10 | `config.py` MARKS_GRADE_BANDS |
| 80.0 | A+ | 9 | `config.py` |
| 70.0 | A | 8 | `config.py` |
| 60.0 | B+ | 7 | `config.py` |
| 50.0 | B | 6 | `config.py` |
| 40.0 | C | 5 | `config.py` |
| <40.0 | F | 0 | `config.py` MARKS_GRADE_FAIL |

### Attendance Thresholds

| Constant | Value | Meaning | Source |
|---:|---|---|---|
| FACULTY_ATTENDANCE_THRESHOLD | 75.0 | Eligibility threshold | `config.py` |
| FACULTY_ATTENDANCE_CRITICAL_THRESHOLD | 60.0 | Critical attendance | `config.py` |
| ATTENDANCE_STATUS_GOOD_SPLIT | 80.0 | Average/Good boundary | `config.py` |
| FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD | 90.0 | Excellent attendance | `config.py` |

### Performance Thresholds

| Constant | Value | Meaning | Source |
|---:|---|---|---|
| FACULTY_PERFORMANCE_THRESHOLD | 60.0 | Performance threshold | `config.py` |
| CRITICAL_PERFORMANCE_THRESHOLD | 50.0 | Critical performance | `config.py` |
| STUDENT_STRENGTH_STRONG_MIN | 75.0 | Strong subject | `config.py` |
| STUDENT_STRENGTH_GOOD_MIN | 60.0 | Good subject | `config.py` |
| STUDENT_NEEDS_ATTENTION_MAX | 45.0 | Needs attention | `config.py` |
| STUDENT_ASSESSMENT_GAP_DROP | 20.0 | Gap detection threshold | `config.py` |
| STUDENT_TREND_STABLE_TOLERANCE | 0.1 | Trend stability | `config.py` |

### Health Score Weights (MD-05)

| Component | Weight | Source |
|---|---:|---|
| HEALTH_ATTENDANCE_WEIGHT | 0.30 | `config.py` |
| HEALTH_PERFORMANCE_WEIGHT | 0.35 | `config.py` |
| HEALTH_PROGRESS_WEIGHT | 0.20 | `config.py` |
| HEALTH_CONSISTENCY_WEIGHT | 0.15 | `config.py` |

### Health Score Bands

| Min Score | Band | Source |
|---:|---|---|
| 80.0 | Excellent | `config.py` HEALTH_EXCELLENT_MIN |
| 65.0 | Good | `config.py` HEALTH_GOOD_MIN |
| 50.0 | Watch | `config.py` HEALTH_WATCH_MIN |
| <50.0 | Needs Attention | `config.py` |

### Career Readiness Weights (MD-06 API)

| Component | Weight | Source |
|---|---:|---|
| CAREER_ACADEMIC_WEIGHT | 0.30 | `config.py` |
| CAREER_CONSISTENCY_WEIGHT | 0.15 | `config.py` |
| CAREER_ALIGNMENT_WEIGHT | 0.20 | `config.py` |
| CAREER_ATTENDANCE_WEIGHT | 0.15 | `config.py` |
| CAREER_INTERNSHIP_WEIGHT | 0.10 | `config.py` |
| CAREER_READINESS_WEIGHT | 0.10 | `config.py` |

### Career Readiness Bands

| Min Score | Band | Source |
|---:|---|---|
| 80.0 | Strong | `config.py` CAREER_READINESS_STRONG_MIN |
| 60.0 | Good | `config.py` CAREER_READINESS_GOOD_MIN |
| 40.0 | Developing | `config.py` CAREER_READINESS_DEVELOPING_MIN |
| <40.0 | Needs Attention | `config.py` |

### M4 Engine Weights (Rule-Based Scoring)

| Component | Max Points | Source |
|---|---:|---|
| Academic Performance | 35 | `ml/src/m4/engine.py` |
| Growth Trend | 10 | `ml/src/m4/engine.py` |
| Career Preparedness | 25 | `ml/src/m4/engine.py` |
| Lifestyle & Discipline | 30 | `ml/src/m4/engine.py` |

### M4 Engine Level Thresholds

| Min Score | Level | Source |
|---:|---|---|
| 75 | High | `ml/src/m4/engine.py` |
| 50 | Medium | `ml/src/m4/engine.py` |
| <50 | Low | `ml/src/m4/engine.py` |

### M4 Scale Function Parameters

| Component | lo | hi | max_points | Source |
|---|---:|---:|---:|---|
| academic_percentage | 40 | 95 | 20 | `engine.py` |
| academic_attendance | 50 | 95 | 10 | `engine.py` |
| lifestyle_study | 0 | 12 | 10 | `engine.py` |

### M4 Ordinal Mappings

| Mapping | Values | Source |
|---|---|---|
| attendance_commitment | Poor→2, Average→5, Good→7, Very Good→9, Excellent→10 | `engine.py` |
| mental_wellbeing | Poor→0, Average→2.5, Good→4, Excellent→5 | `engine.py` |
| stress_level | Very High→0, High→1, Medium→3, Low→5 | `engine.py` |
| physical_activity | Never→0, Rare→0.7, Moderate→1.4, Regular→2.0 | `engine.py` |
| placement_readiness | Low→25, Medium→50, High→75, Excellent→100 | `student_career_rules.py` |

### M3 Risk Thresholds

| Threshold | Meaning | Source |
|---|---|---|
| probability >= 0.7 | High risk | `ml/v2/m3_at_risk_prediction/inference/predictor.py` |
| probability >= threshold (tuned) | Medium risk (is_estimated_at_risk) | `ml/v2/m3_at_risk_prediction/inference/predictor.py` |
| probability < threshold | Low risk | `ml/v2/m3_at_risk_prediction/inference/predictor.py` |

### Workload Weights (Faculty)

| Component | Weight | Source |
|---|---:|---|
| WORKLOAD_RESOURCE_UTIL_WEIGHT | 0.4 | `config.py` |
| WORKLOAD_RESOURCE_BALANCE_WEIGHT | 0.3 | `config.py` |
| WORKLOAD_RESOURCE_COVERAGE_WEIGHT | 0.2 | `config.py` |
| WORKLOAD_RESOURCE_EFFICIENCY_WEIGHT | 0.1 | `config.py` |

---

## 17. Batch / Semester / Academic-Year Effects

### Filter Application

- **Batch:** Filtered by `students.admission_year` (starting cohort year). Applied in SQL WHERE clauses.
- **Semester:** Filtered by `semester_summary.semester_no` (1-8). Applied in SQL WHERE clauses.
- **Academic Year:** Filtered by `semester_summary.academic_year` (e.g., "2026-27"). Applied in SQL WHERE clauses.
- **Department:** Filtered by `students.department_code`. Applied in SQL WHERE clauses.

### Impact on Predictions

- **M1 V2:** Features are point-in-time (semester ≤ current_semester). Batch/department filtering affects which students are in scope.
- **M2 V2 / M3 V2:** Same temporal constraint. Observation semester T is determined from the most recent completed semester.
- **M4:** Academic aggregates are computed from ALL completed semesters for the student. No batch/semester filtering within the student.

### Cohort Guard (M1 V2)

M1 V2 inference rejects non-STU6A students (would fabricate 0.0 predictions). This is a hard filter in the predictor.

### Batch ≠ Academic Year

- **Batch** = student starting/admission cohort (e.g., "2023" batch started in 2023)
- **Academic Year** = the year in which academic records exist (e.g., "2026-27")
- These are independent dimensions. A student from batch "2023" can have records in academic year "2026-27".

---

## 18. GenAI Explanation Layer

### Architecture

Source: `backend/app/services/genai_provider.py`, `backend/app/services/genai_service.py`

**GenAI does NOT make predictions.** It only generates narrative explanations of existing structured prediction/analytics results.

### GenAI Provider

- Primary: Groq API (model: `openai/gpt-oss-120b`)
- Fallback: Ollama local (model: `qwen2.5:3b`)
- OpenAI-compatible interface via `httpx`

### GenAI Service

Source: `backend/app/services/genai_service.py`

The `GenAIService` provides:
1. **Prediction explanations** — takes structured prediction results and generates human-readable explanations
2. **Chat responses** — answers student questions using context from their academic data
3. **Insight generation** — creates narrative summaries of analytics data

### Prompt Construction

For prediction explanations, the service:
1. Receives structured prediction data (M1 marks, M2 SGPA, M3 risk, M4 career score)
2. Injects it into a prompt template
3. Sends to GenAI provider
4. Returns narrative text

### Chat Orchestration

Source: `backend/app/services/chat_orchestrator.py`

- Routes student questions to appropriate data sources
- Fetches relevant academic data
- Constructs context-aware prompts
- Returns GenAI-generated responses
- Blocks certain requests (code generation, accessing other students' data, API key requests)

### Intent Router

Source: `backend/app/services/intent_router.py`

Classifies student messages into intents:
- academic_query
- attendance_query
- prediction_query
- career_query
- general_query
- blocked_request

---

## 19. Example Calculations

### Example 1: Marks Derivation

**Input:** internal_marks=15, mid_sem_marks=35, end_sem_marks=45

```
total = 15 + 35 + 45 = 95
percentage = 95 / 140 × 100 = 67.86%
grade = "B+" (≥60%)
grade_point = 7
result_status = "Pass" (67.86% ≥ 40% AND 45 ≥ 18)
performance_category = "Average" (≥60%)
remarks = "Satisfactory performance" (≥60%)
```

### Example 2: Attendance Status

**Input:** attendance_percentage=72%

```
status = "Low" (60% ≤ 72% < 75%)
eligibility = "Not Eligible" (72% < 75%)
shortage_flag = "Yes" (72% < 75%)
```

### Example 3: M4 Career Readiness Score

**Input:** avg_pct=75, avg_att=82, backlogs=1, study_hrs=6, stress="Medium", sleep=7.5, internship="Yes", cert="Yes", higher_studies="Yes"

```
Academic (35 pts):
  pct_score = (75-40)/(95-40) × 20 = 12.73
  att_score = (82-50)/(95-50) × 10 = 7.11
  backlog_score = 3 (≤2)
  subtotal = 22.84

Growth Trend (10 pts):
  slope = 1.5 → (1.5+2)/4 × 10 = 8.75

Career Preparedness (25 pts):
  internship = 15, cert = 5, planning = 5 → 25

Lifestyle (30 pts):
  study = 6/12 × 10 = 5.0
  att_commit = 7 (Good)
  wellbeing = 4 (Good)
  sleep = 3 (7.5h)
  activity = 1.4 (Moderate)
  subtotal = 20.4

Final = 22.84 + 8.75 + 25 + 20.4 = 76.99
Level = "High" (≥75)
```

### Example 4: Academic Health Score

**Input:** attendance=82%, percentages=[70,65,80,72], semester_pct=75, sgpas=[7.5,7.8,7.2]

```
attendance = 82.0 (w=0.30)
performance = 71.75 (w=0.35)
progress = 75.0 (w=0.20)
consistency = 100 - 2.646×10 = 97.35 (w=0.15)

score = (82×0.30 + 71.75×0.35 + 75×0.20 + 97.35×0.15) / 1.0 = 79.31
band = "Good" (65 ≤ 79.31 < 80)
```

### Example 5: Attendance What-If

**Input:** total=100, attended=70, present=10, absent=5, target=75%

```
current = 70/100 × 100 = 70%
new_total = 100 + 10 + 5 = 115
new_attended = 70 + 10 = 80
resulting = 80/115 × 100 = 69.57%

classes_to_reach_target = ceil((0.75×100 - 70) / (1-0.75)) = ceil(5/0.25) = 20 classes
```

---

## 20. Limitations & Implementation Gaps

### ML Model Gaps

1. **M1 V1 / M2 V1 / M3 V1 artifacts** — Trained on 80 synthetic students. Metrics are inflated. Status: REBUILD.
2. **M3 V1 validation gate** — Blocked due to insufficient positive-class statistical coverage.
3. **M3 V2 threshold** — Tuned on group-validation probabilities. Exact threshold value is stored in the model artifact, not documented externally.
4. **M1 V2 feature importance** — Ridge coefficients are available but not exposed in the API response.
5. **M4 ML-based classifier** — Training code exists (`ml/src/m4/train_m4.py`) but is NOT used in production. Production M4 uses rule-based engine only.
6. **V3 (synthetic M1)** — Trained on local CSV, not Supabase. Limited production compatibility (attendance_percentage not available for legacy 80 students).

### Formula Gaps

1. **subject_domain one-hot columns** — The exact mapping of subject names to domains for M1 V2 is defined in the feature builder but the complete keyword list is not fully enumerated in config.
2. **M4 percentage_trend_slope** — Computed via `np.polyfit(semesters, percentages, 1)[0]`. The slope value is not bounded in the code (could exceed [-2, +2] range).
3. **M4 sleep_score** — Uses hardcoded thresholds (7-9→3, 6-7/9-10→2, etc.) in the engine, not configurable via settings.

### Database-Derived Values (No Formula Applied)

The following values are retrieved directly from the database with no formula applied in the application layer:
- `students.cgpa`
- `students.current_semester`
- `semester_summary.sgpa` (used as-is in analytics)
- `semester_summary.percentage` (used as-is in analytics)
- `career_preferences.placement_readiness_level` (mapped to score only in M4/MD-06)
- `student_lifestyle_survey.daily_study_hours` (used as-is or mapped in M4)

### Unimplemented Features

1. **M5** — No M5 module exists.
2. **Model versioning** — V1/V2/V3 coexist but no automated version promotion.
3. **A/B testing** — No infrastructure for comparing model versions in production.
4. **Real-time prediction** — All predictions are on-demand (not pre-computed or scheduled).

---

## 21. Master Calculation & Prediction Table

| ID | Feature | Type | Inputs | Formula/Model | Output | Source |
|---|---|---|---|---|---|---|
| M1 V1 | Subject Marks | ML Prediction | internal, mid, attendance, credits, etc. | hist_gbm | end_sem_marks (0-70) | `ml/artifacts/models/m1_subject_endmarks.joblib` |
| M1 V2 | Subject Marks | ML Prediction | 39 features (see §12) | Ridge Regression | end_sem_marks, grade_band | `ml/v2/m1_subject_prediction/` |
| M1 V3 | Subject Marks | ML Prediction | 8 features | Linear Regression | end_sem_marks | `ml/v3/m1_subject_prediction/` |
| M2 V1 | Next Semester | ML Prediction | sgpa, percentage, attendance, etc. | hist_gbm | next_sgpa, next_pct | `ml/artifacts/models/m2_next_semester_performance.joblib` |
| M2 V2 | Next Semester | ML Prediction | semester T features (see §6) | Ridge Regression | next_sgpa, next_pct, bands | `ml/v2/m2_next_semester_prediction/` |
| M3 V1 | At-Risk | ML Prediction | same as M2 + failed_count | hist_gbm | is_at_risk (blocked) | `ml/artifacts/models/m3_next_semester_at_risk.joblib` |
| M3 V2 | At-Risk | ML Prediction | same as M2 + failed_count | LR/RF/GBM/XGB | probability, threshold, risk_level | `ml/v2/m3_at_risk_prediction/` |
| M4 | Career Readiness | Rule-Based | academic, career, lifestyle data | Weighted scoring (35+10+25+30) | score 0-100, level | `ml/src/m4/engine.py` |
| MD-03 | Performance Trends | Rule-Based | semester summaries | delta computation | direction, interpretation | `student_analytics_rules.py` |
| MD-03 | Subject Strengths | Rule-Based | performance rows | threshold bands | Strong/Good classification | `student_analytics_rules.py` |
| MD-03 | Needs Attention | Rule-Based | performance rows | priority rules | flagged subjects | `student_analytics_rules.py` |
| MD-03 | Learning Gaps | Rule-Based | performance rows | progression analysis | gap signals | `student_analytics_rules.py` |
| MD-03 | Class Benchmark | Rule-Based | student + class averages | difference computation | comparison result | `student_analytics_rules.py` |
| MD-04 | Attendance What-If | Rule-Based | attendance counts | projection formula | resulting_attendance, classes_needed | `student_analytics_rules.py` |
| MD-05 | Academic Health | Rule-Based | attendance, performance, progress, consistency | Weighted avg (0.30+0.35+0.20+0.15) | score 0-100, band | `student_health_rules.py` |
| MD-05 | Focus Priorities | Rule-Based | health signals | severity ranking | top 3 priority items | `student_health_rules.py` |
| MD-06 | Career Readiness | Rule-Based | academic, consistency, alignment, attendance, internship, readiness | Weighted avg (0.30+0.15+0.20+0.15+0.10+0.10) | score 0-100, band | `student_career_rules.py` |
| MD-06 | Domain Alignment | Rule-Based | completed subjects, preferred domain | keyword matching | alignment % | `student_career_rules.py` |
| - | Marks Derivation | Formula | internal, mid, end marks | total/140×100, grade bands | total, pct, grade, result | `faculty_service.py` |
| - | Attendance Status | Formula | attendance percentage | threshold bands | status, eligibility, shortage | `faculty_service.py` |
| - | Grade Lookup | Formula | percentage | band thresholds | grade, grade_point | `config.py` |
| - | Performance Category | Formula | percentage | band thresholds | category | `config.py` |
| - | Remarks | Formula | percentage | band thresholds | remarks text | `config.py` |
| - | Workload Health | Formula | utilization, balance, coverage, efficiency | weighted sum (0.4+0.3+0.2+0.1) | health score | `faculty_service.py` |
| - | Notification Rules | Rule-Based | attendance, results, backlogs, risk | threshold checks | notification events | `notification_rules.py` |
| GenAI | Prediction Explanation | GenAI | structured prediction results | LLM prompt | narrative text | `genai_service.py` |
| GenAI | Chat Response | GenAI | student question + academic context | LLM prompt | narrative text | `chat_orchestrator.py` |
| GenAI | Insight Generation | GenAI | analytics data | LLM prompt | narrative summary | `genai_service.py` |

---

## 22. Source Code Reference

### ML Models
| File | Key Functions |
|---|---|
| `ml/v2/m1_subject_prediction/inference/predictor.py` | `M1V2Predictor.predict()` |
| `ml/v2/m1_subject_prediction/features/builder.py` | `M1FeatureBuilder.build_features()` |
| `ml/v2/m1_subject_prediction/preprocessing/pipeline.py` | `M1Preprocessor` |
| `ml/v2/m1_subject_prediction/config.py` | All M1 V2 constants, feature lists |
| `ml/v2/m2_next_semester_prediction/inference/predictor.py` | `M2V2Predictor.predict()` |
| `ml/v2/m2_next_semester_prediction/features/builder.py` | `M2FeatureBuilder.build_features()` |
| `ml/v2/m2_next_semester_prediction/config.py` | All M2 V2 constants |
| `ml/v2/m3_at_risk_prediction/inference/predictor.py` | `M3V2Predictor.predict()` |
| `ml/v2/m3_at_risk_prediction/features/builder.py` | `M3FeatureBuilder.build_features()` |
| `ml/v2/m3_at_risk_prediction/config.py` | All M3 V2 constants |
| `ml/src/m4/engine.py` | `CareerReadinessEngine.score()`, `score_academic_performance()`, `score_growth_trend()`, `score_career_preparedness()`, `score_lifestyle_discipline()` |
| `ml/src/features/v1_inference_contract.py` | `predict_m1()`, `predict_m2()`, `predict_m3()`, `MODEL_READINESS` |
| `ml/src/registry.py` | `load_model()`, `ModelEntry` |
| `ml/src/inference.py` | `InferenceService.predict_m1/m2/m3/m4()` |
| `ml/src/prediction_service.py` | `PredictionService`, `fetch_m1_raw_data()`, `fetch_m2m3_raw_data()`, `fetch_m4_raw_data()` |
| `ml/src/explain.py` | `ExplanationService.explain()` |
| `ml/src/feature_config.py` | Feature definitions, forbidden features |

### Backend Services
| File | Key Functions |
|---|---|
| `backend/app/services/student_analytics_rules.py` | `compute_trends()`, `compute_strengths()`, `compute_needs_attention()`, `compute_learning_gaps()`, `compute_benchmark()`, `compute_attendance_what_if()` |
| `backend/app/services/student_health_rules.py` | `compute_health_score()`, `compute_priorities()` |
| `backend/app/services/student_career_rules.py` | `compute_career_readiness()`, `compute_domain_alignment()`, `subject_is_relevant()` |
| `backend/app/services/faculty_service.py` | `derive_marks_fields()`, `attendance_aggregate_fields()`, `_health_score()` |
| `backend/app/services/analytics_service.py` | All analytics query methods |
| `backend/app/services/admin_ml_service.py` | Admin ML overview, model status |
| `backend/app/services/prediction_generation_service.py` | `generate_and_persist()`, `get_latest()`, `get_history()` |
| `backend/app/services/prediction_insights_service.py` | `get_student_insights()` |
| `backend/app/services/prediction_contract_service.py` | V1 contract adapter |
| `backend/app/services/m1v2_prediction_service.py` | `M1V2PredictionService.predict()` |
| `backend/app/services/m2v2_prediction_service.py` | `M2V2PredictionService.predict()` |
| `backend/app/services/m3v2_prediction_service.py` | `M3V2PredictionService.predict()` |
| `backend/app/services/genai_service.py` | `GenAIService` |
| `backend/app/services/chat_orchestrator.py` | `ChatOrchestrator` |
| `backend/app/services/notification_rules.py` | Notification generation rules |

### API Endpoints
| File | Key Endpoints |
|---|---|
| `backend/app/api/v1/predict.py` | `/predict/m1/{id}`, `/predict/m1v2/{id}`, `/predict/m1v3/{id}`, `/predict/m2/{id}`, `/predict/m2v2/{id}`, `/predict/m3/{id}`, `/predict/m3v2/{id}`, `/predict/m4/{id}`, `/predict/insights/{id}` |
| `backend/app/api/v1/analytics.py` | `/analytics/students/{id}/*`, `/analytics/subjects/{id}/*`, `/analytics/departments/*`, `/analytics/at-risk/*` |
| `backend/app/api/v1/admin.py` | Admin ML intelligence, dashboard |
| `backend/app/api/v1/student.py` | Student analytics, health, career, predictions |
| `backend/app/api/v1/faculty.py` | Faculty analytics, workload, marks entry |

### Configuration
| File | Contents |
|---|---|
| `backend/app/core/config.py` | All thresholds, weights, bounds, grade bands |

### Repositories
| File | Purpose |
|---|---|
| `backend/app/repositories/analytics_repo.py` | Analytics SQL queries |
| `backend/app/repositories/ml_prediction_repo.py` | Prediction CRUD |
| `backend/app/repositories/student_repo.py` | Student data queries |
| `backend/app/repositories/admin_repo.py` | Admin data queries |
| `backend/app/repositories/faculty_repo.py` | Faculty data queries |

### ETL
| File | Purpose |
|---|---|
| `backend/etl/` | 7-stage ETL pipeline (extract, validate, derive, transform, stitch, load, stage) |

---

*Document generated from source code inspection. No application code was modified; only this documentation file was created.*
