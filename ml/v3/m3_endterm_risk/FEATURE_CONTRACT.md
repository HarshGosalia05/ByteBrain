# M3 v3 Feature Contract — Same-Semester End-Term Risk Prediction

**Model**: `m3_v3_endterm_risk` (v3.0)  
**Algorithm**: `HistGradientBoostingClassifier` (`hist_gbm`)  
**Task**: Same-Semester Mid-Sem to End-Term Academic Risk Prediction  
**Target**: `is_at_risk_end_sem` (binary: 0 = Normal, 1 = At-Risk)  
**Tuned Decision Threshold**: `0.330`  
**Feature Count**: 27 numeric features  

---

## 1. Problem Formulation & Prediction Point

- **Business Requirement**:
  - Predict whether a student will enter an academic-risk state (backlog/ATKT) in the **same semester's end-term** examination.
  - CSE: Semester 7 Mid-Sem $\rightarrow$ Semester 7 End-Term
  - BBA: Semester 5 Mid-Sem $\rightarrow$ Semester 5 End-Term
- **Prediction Point**:
  - Immediately following the completion of mid-semester examinations for semester $T$.
  - Only features available on or before the mid-semester milestone are permitted.
  - Observation Semester $T ==$ Target Semester $T$.

---

## 2. Target Definition

| Property | Value |
|---|---|
| **Target Variable** | `is_at_risk_end_sem` |
| **Type** | Binary integer (`0` or `1`) |
| **Definition** | `is_at_risk_end_sem = 1 if semester_result(T) in ('FAIL', 'ATKT') OR backlog_count(T) > 0 else 0` |
| **Source Tables** | `student_semester_summary` (result status and backlog count at semester $T$) |
| **Class Distribution** | 2.70% positive (227 / 8,400 transitions across 1,200 CSE students in semesters 1–7) |

---

## 3. Feature Contract (27 Features in Exact Order)

Features must be fed to the model in the exact 27-column ordering defined below:

### Tier 1A: Mid-Semester Subject Performance (4 features)
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 1 | `subj_mid_sem_marks_mean` | `student_subject_performance` | float | Mean mid-term examination marks across subjects at $T$ ($0–50$) |
| 2 | `subj_mid_sem_marks_std` | `student_subject_performance` | float | Standard deviation of mid-term marks across subjects at $T$ |
| 3 | `subj_internal_marks_mean` | `student_subject_performance` | float | Mean internal marks across subjects at $T$ ($0–20$) |
| 4 | `subj_internal_marks_std` | `student_subject_performance` | float | Standard deviation of internal marks across subjects at $T$ |

### Tier 1B: Continuous Assessment & Submission Signals (4 features)
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 5 | `subj_assignment_score_mean` | `student_subject_performance` | float | Mean assignment score at $T$ ($0–100$) |
| 6 | `subj_quiz_avg_marks_mean` | `student_subject_performance` | float | Mean quiz score at $T$ ($0–100$) |
| 7 | `subj_submission_delay_mean` | `student_subject_performance` | float | Mean days of assignment/project submission delay at $T$ ($\ge 0$) |
| 8 | `subj_pre_endsem_pct_mean` | `student_subject_performance` | float | Pre-endsem cumulative assessment score percentage ($0–100$) |

### Tier 1C: Semester Attendance Signals (3 features)
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 9 | `semester_attendance_percentage` | `student_semester_summary` / `attendance` | float | Attendance percentage up to mid-sem at $T$ ($0–100$) |
| 10 | `att_tsem_total_pct` | `attendance` | float | Percentage of attended sessions over held sessions ($0–100$) |
| 11 | `att_tsem_low_pct_weeks` | `attendance_weekly` | float | Ratio of weeks with $<75\%$ attendance up to mid-sem ($0–1$) |

### Tier 1D: Learning Activity Signals (4 features)
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 12 | `learn_tsem_volume_total` | `student_learning_activity` | float | Total learning LMS activity actions in semester $T$ ($\ge 0$) |
| 13 | `learn_tsem_engagement_mean` | `student_learning_activity` | float | Mean weekly LMS engagement consistency score ($0–1$) |
| 14 | `learn_tsem_completion_mean` | `student_learning_activity` | float | Mean assessment completion rate on LMS ($0–1$) |
| 15 | `learn_tsem_late_mean` | `student_learning_activity` | float | Mean late submission rate on LMS ($0–1$) |

### Tier 1E: Prior History Before Semester T (7 features)
*Note: Computed strictly on completed semesters $< T$. If $T=1$, all values default to NaN and are imputed.*
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 16 | `previous_sem_sgpa` | `student_semester_summary` | float | SGPA achieved in prior semester $T-1$ ($0–10$) |
| 17 | `sgpa_drift` | `student_semester_summary` | float | Drift: $\text{SGPA}(T-1) - \text{SGPA}(T-2)$ |
| 18 | `sgpa_rolling_mean_3` | `student_semester_summary` | float | 3-semester rolling SGPA mean prior to $T$ ($0–10$) |
| 19 | `previous_sem_backlog_count` | `student_semester_summary` | float | Active backlogs incurred in prior semester $T-1$ ($\ge 0$) |
| 20 | `backlog_change` | `student_semester_summary` | float | Backlog delta: $\text{Backlog}(T-1) - \text{Backlog}(T-2)$ |
| 21 | `cumulative_backlog_events` | `student_semester_summary` | float | Total cumulative backlogs accumulated before semester $T$ ($\ge 0$) |
| 22 | `attendance_aggregate_pct` | `student_semester_summary` | float | Historical aggregate attendance rate before semester $T$ ($0–100$) |

### Tier 1F: Academic Structure & Enrollment (2 features)
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 23 | `credits_registered` | `student_semester_summary` | float | Total academic credits registered in semester $T$ |
| 24 | `subjects_registered` | `student_semester_summary` | float | Number of registered subjects in semester $T$ |

### Tier 1G: Student Demographics & Survey (3 features)
| # | Feature Name | Source Table | Type | Range / Description |
|---|---|---|---|---|
| 25 | `semester_no` | `students` / `student_semester_summary` | float | Current academic semester number $T$ ($1–7$) |
| 26 | `is_male` | `students.gender` | int | Binary gender encoding: `1` for Male, `0` for Female / Other |
| 27 | `stress_ordinal` | `student_lifestyle_survey` | int | Encoded self-reported stress: Low=`0`, Medium=`1`, High=`2` |

---

## 4. Forbidden Features (Anti-Leakage Policy)

The following columns encode end-semester outcomes or future information. **Any presence in the feature matrix causes the fail-closed leakage gate to abort execution**:

1. **Current Semester End-Term Academic Outcomes**:
   - `is_at_risk_end_sem` (target)
   - `semester_sgpa` (final SGPA at $T$)
   - `semester_percentage` (final overall % at $T$)
   - `semester_total_marks`
   - `semester_result` (`PASS`, `FAIL`, `ATKT`)
   - `end_semester_grade`
   - `backlog_count` (end-term backlog count defines the target)
   - `credits_earned` (known only after end-term evaluations)
2. **Current Semester End-Term Subject Marks**:
   - `end_sem_marks`
   - `subj_end_sem_marks_mean`
   - `subj_end_sem_marks_std`
   - `subj_failed_subjects_count`
3. **Future Semesters ($T+1$)**:
   - Any column with prefix `next_semester_`, `next_sem_`, or `next_`
   - `is_at_risk_next_sem`
4. **Post-Graduation & Placement**:
   - `placement_status`, `package_lpa`, `package_tier`, `placement_domain`, `placement_date`

---

## 5. Missing Data & Imputation Policy

- **Discipline**: Fit-on-train-only `SimpleImputer(strategy="median")`.
- **Inference Robustness**: When optional survey or LMS signals are missing, the preprocessor fills with training set medians without hallucinating values.
- **Fail Boundary**: If a student is currently in the final degree semester (e.g. Semester 8 for CSE), the service returns `readiness_status = "NO_DATA"` with explanation rather than making invalid forward projections.
