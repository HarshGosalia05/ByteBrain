# M4 — Career Readiness Score: Final Report

## 1. Status

**M4 is a deterministic, rule-based scoring engine — it is NOT a machine learning model.**

- No model is trained.
- No `.joblib` (or any other model artifact / pickle) is created or required.
- Every point awarded to every student can be traced back, line by line, to a raw value in the source CSVs.
- Re-running the script on the same input data produces **byte-for-byte identical output** every time (verified — see §6).

This replaces the earlier supervised-ML version of M4, which trained against `placement_readiness_level`. That target was found to be **synthetically / deterministically derived** (not a genuine outcome label), so any model trained or calibrated against it would have been learning the synthetic generation rule rather than real career readiness. M4 was rebuilt from scratch as a transparent rules engine to eliminate this dependency entirely.

## 2. File locations

| Item | Path |
|---|---|
| Implementation | `ml/src/m4/m4_career_readiness.py` |
| Input data (read-only) | `ml/data/raw/*.csv` |
| Output | `ml/data/final/m4_career_readiness_scores.csv` |
| This report | `ml/reports/m4_report.md` |

The script resolves all paths relative to its own location (`ml/src/m4/` → project root `ml/` is two levels up), so it runs correctly regardless of the current working directory:

```bash
python ml/src/m4/m4_career_readiness.py
```

## 3. Datasets used

| File | Rows | Role |
|---|---|---|
| `students_rows.csv` | 80 | Identity / demographic fields only (name, department, current semester) |
| `student_semester_summary_rows.csv` | 500 (80 students × 5–7 completed semesters) | Real, per-semester academic marks — the basis for the Academic Performance and Growth Trend components |
| `career_preferences_rows.csv` | 80 | Career intent & preparation signals |
| `lifestyle_survey_rows.csv` | 80 | Habits, discipline, and wellbeing signals |

## 4. Exact features used (and explicitly excluded)

### 4.1 Used from `students_rows.csv`
`student_id`, `enrollment_no`, `full_name`, `department_name`, `current_semester` — identity/display fields only, **no academic or readiness signal is taken from this file.**

### 4.2 Used from `student_semester_summary_rows.csv`
`semester_no`, `semester_percentage`, `semester_sgpa`, `semester_attendance_percentage`, `backlog_count`, `semester_result` — real, per-semester completed records, aggregated per student into:
- `avg_semester_percentage`, `avg_semester_attendance`
- `total_backlogs_computed` (engine's own sum of `backlog_count` — deliberately renamed from `total_backlogs` so it is never confused with the poisoned students-table column of the same name)
- `percentage_trend_slope` (linear slope of `semester_percentage` vs `semester_no`)
- `first_semester_percentage`, `last_semester_percentage`

### 4.3 Used from `career_preferences_rows.csv`
`internship_completed`, `certification_interest`, `higher_studies_interest`, `entrepreneurship_interest`

### 4.4 Used from `lifestyle_survey_rows.csv`
`daily_study_hours`, `attendance_commitment`, `mental_wellbeing`, `stress_level`, `average_sleep_hours`, `physical_activity`

### 4.5 Explicitly excluded ("poisoned") columns — never read into the scoring logic

Dropped immediately after load, as a hard safety net (so they cannot leak in even if the file is edited later):

**From `students_rows.csv`:**
`latest_sgpa`, `overall_cgpa`, `overall_percentage`, `overall_attendance_percentage`, `total_backlogs`, `academic_standing`

**From `career_preferences_rows.csv`:**
`placement_readiness_level` — synthetic/deterministically-derived label. **Not used to build, calibrate, or tune any part of the score.**

## 5. Scoring framework (100 points total)

| Component | Weight | Sub-components |
|---|---|---|
| **A. Academic Performance** | 35 pts | Avg semester % (20) + avg attendance (10) + backlog record (5) |
| **B. Academic Growth Trend** | 10 pts | Slope of semester % across completed semesters |
| **C. Career Preparedness** | 25 pts | Internship completed (15) + certification focus (5) + forward planning (5) |
| **D. Lifestyle & Discipline** | 30 pts | Study hours (10) + self-reported attendance commitment (10) + wellbeing (5) + sleep (3) + physical activity (2) |
| **Total** | **100 pts** | |

### A. Academic Performance (35 pts)
- **Percentage score (0–20):** `avg_semester_percentage` linearly scaled from [40, 95] → [0, 20]
- **Attendance score (0–10):** `avg_semester_attendance` linearly scaled from [50, 95] → [0, 10]
- **Backlog score (0–5):** 0 backlogs → 5 pts; 1–2 → 3 pts; 3–4 → 1 pt; 5+ → 0 pts

### B. Academic Growth Trend (10 pts)
Linear regression slope of `semester_percentage` vs `semester_no`. Slope ≥ +2 → 10 pts (full marks); slope ≤ −2 → 0 pts; linear interpolation in between. Students with only one recorded semester get a neutral 5 pts (no history to judge a trend from) — not applicable in this dataset, as all 80 students have ≥5 completed semesters.

### C. Career Preparedness (25 pts)
- **Internship (0/15):** `internship_completed == Yes` → 15 pts
- **Certification focus (0/5):** a named certification/skill track present → 5 pts
- **Forward planning (0/5):** `higher_studies_interest == Yes` OR `entrepreneurship_interest == Yes` → 5 pts

### D. Lifestyle & Discipline (30 pts)
- **Study hours (0–10):** `daily_study_hours` linearly scaled from [1, 6] → [0, 10]
- **Attendance commitment (0–10):** mapped — Poor=2, Average=5, Good=7, Very Good=9, Excellent=10
- **Wellbeing (0–5):** average of mental-wellbeing map (Poor=0, Average=2.5, Good=4, Excellent=5) and stress-level map (Very High=0, High=1, Medium=3, Low=5)
- **Sleep (0–3):** 7–9 hrs → 3; 6–7 or 9–10 hrs → 2; 5–6 or 10–11 hrs → 1; else 0
- **Physical activity (0–2):** Never=0, Rare=0.7, Moderate=1.4, Regular=2

## 6. Level thresholds (fixed policy — not tuned against any label)

| Score | Level |
|---|---|
| ≥ 75 | **High** |
| 50 – 74.99 | **Medium** |
| < 50 | **Low** |

These thresholds were set as a fixed, principled policy decision (round numbers dividing the 0–100 range into three readiness bands) and were **not** adjusted to match `placement_readiness_level` or any other synthetic label.

## 7. Validation checks (run automatically, printed on every execution)

| # | Check | Result |
|---|---|---|
| 1 | Score is within 0–100 for all students | **PASS** |
| 2 | No poisoned columns present in scoring data | **PASS** |
| 3 | `placement_readiness_level` not used anywhere in scoring logic | **PASS** |
| 4 | Levels restricted to Low/Medium/High | **PASS** |
| 5 | `positive_factors` and `risk_factors` generated for every student | **PASS** |
| 6 | Re-computation on same input yields identical scores (deterministic) | **PASS** |
| 7 | Raw CSVs opened in read-only mode only (`pd.read_csv`, no writes) | **PASS** |

**Additional manual verification performed:**
- Ran the script twice independently and diffed the two output CSVs — **byte-for-byte identical.**
- Searched the entire `ml/` project tree for `*.joblib`, `*.pkl`, `*.pickle` — **none found.**
- Compared MD5 checksums of the raw CSVs before and after running the script — **unchanged** (raw files are never opened in write mode).

## 8. Results summary

- **Students scored:** 80 / 80
- **Score range:** 13.15 – 94.41
- **Mean:** 64.34 | **Median:** 70.82
- **Level distribution:** High = 19, Medium = 46, Low = 15
- **Average component contribution:** Academic 23.03/35, Trend 5.04/10, Career 18.12/25, Lifestyle 18.16/30

### Sample results

| student_id | full_name | score | level |
|---|---|---|---|
| STU000033 | Meet Patel | 94.41 | High |
| STU000023 | Diya Desai | 93.82 | High |
| STU000009 | Mahi Modi | 93.64 | High |
| STU000056 | Diya Mehta | 71.20 | Medium |
| STU000050 | Vaidehi Joshi | 70.88 | Medium |
| STU000055 | Aryan Shah | 70.76 | Medium |
| STU000064 | Vaidehi Desai | 16.40 | Low |
| STU000060 | Jiya Soni | 15.15 | Low |
| STU000032 | Jiya Patel | 13.15 | Low |

Example explanation (STU000033, score 94.41, High):
> **positive_factors:** Strong academic record (avg 95.04% across 7 semesters); No academic backlogs recorded; Has completed an internship; Actively planning ahead (higher studies / entrepreneurship interest); Strong daily study habit (6.1 hrs/day); Good mental wellbeing and low stress
> **risk_factors:** No significant risk factors identified

Example explanation (STU000032, score 13.15, Low):
> **positive_factors:** No strong standout positive factors identified
> **risk_factors:** Low average academic percentage (40.33%); 24 academic backlog(s) recorded; Low average semester attendance (55.5%); No internship completed yet; Low daily study hours (1.2 hrs/day); Elevated stress / low wellbeing (stress: Very High, wellbeing: Poor); Self-reported attendance commitment is 'Poor'; Poor sleep pattern (4.4 hrs/night)

Full per-student results with all component sub-scores are in `ml/data/final/m4_career_readiness_scores.csv`.

## 9. Confirmations

- ✅ M4 is rule-based, **not** ML — no training step, no estimator object, no model artifact.
- ✅ No `.joblib` created or required anywhere.
- ✅ Raw CSVs in `ml/data/raw/` were never modified (read-only access, verified via checksum).
- ✅ M1/M2/M3 and backend/frontend/database/migrations were not touched.
- ✅ `placement_readiness_level` was not used as ground truth, and was not used to build, calibrate, or tune the score in any way.
- ✅ Score is deterministic — identical output across independent runs.
