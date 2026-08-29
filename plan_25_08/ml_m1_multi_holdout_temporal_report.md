# M1 — Multi-Holdout Temporal Validation Report

## 1. Objective
Measure whether the M1 subject-end-semester-mark predictor generalizes across a
**spread of future-semester boundaries**, not just a single hold-out. This is an
evaluation/calibration step only: no model improvement, no selection change, no
artifact writes.

## 2. Existing M1 contract (unchanged, reused)
- **Target:** `end_sem_marks` (0–70), grain `(student_id, subject_id, semester_no)`.
- **Stage-A feature contract:** 8 raw → 12 encoded columns
  (`internal_marks`, `mid_sem_marks`, `attendance_percentage`, `credits`,
  `semester_no`, 4× `subject_type_*`, 2× `department_name_*`, `is_male`).
- **Candidates:** ridge, hist_gbm, xgboost (`config.MODEL_ALGORITHMS`), exact
  canned hyperparameters in `evaluate.make_model`.
- **Metrics:** MAE, RMSE, R², predictions clipped to `[0,70]`.
- **Baseline (GroupKFold(5) by student × 3 seeds):** hist_gbm MAE 3.181,
  RMSE 3.837, R² 0.8168 (unchanged).
- **Selected model remains:** HistGradientBoosting.
- **Dataset:** 3293 training (labeled) / 557 deployment rows, 80 students.
- **Deployment boundary:** semester 7 (target NULL) — kept excluded.

## 3. Temporal-window methodology
Windows of the form `TRAIN: semesters ≤ k` → `VALID: semester k+1`. All training
semesters are strictly earlier than the validation semester; deployment rows are
excluded; preprocessing is fit on training only; each window is deterministic.

## 4. Exact windows used (derived from real labeled data)
A semester `v` is a valid validation semester iff it has `≥ 50` labeled rows and
at least one strictly earlier semester. Semester 1 has no earlier semester;
semester 7 (3 rows) fails the volume floor and is the deployment boundary.

| Window | Training semesters | Validation semester |
|---|---|---|
| 1 | 1 | 2 |
| 2 | 1–2 | 3 |
| 3 | 1–3 | 4 |
| 4 | 1–4 | 5 |
| 5 | 1–5 | 6 |

## 5. Data counts per window
| Window | Train rows | Valid rows | Train students | Valid students | Student overlap |
|---|---|---|---|---|---|
| 1 | 610 | 610 | 80 | 80 | 80 |
| 2 | 1220 | 660 | 80 | 80 | 80 |
| 3 | 1880 | 610 | 80 | 80 | 80 |
| 4 | 2490 | 400 | 80 | 50 | 50 |
| 5 | 2890 | 400 | 80 | 50 | 50 |

## 6. Student overlap behavior
Overlap is high (80/80 in early windows, 50/50 in later ones) because this is
TEMPORAL validation for the same population, not student-isolated CV. Overlap is
measured and reported, not artificially eliminated — the invariant that matters
is that every validation semester is strictly later than every training semester
(verified for all windows). No new student-splitting rule was introduced.

## 7. Feature contract
Every window is aligned to the identical **12-column encoded** contract derived
from the full labeled training frame (0-filled for categorical levels absent in
early windows). This guarantees a like-for-like comparison across windows.
Verified: all windows share the exact same encoded feature set; target and
forbidden columns are absent.

## 8. Leakage controls (all PASS)
- validation semester > every training semester (all windows)
- zero train/validation row overlap per window
- `end_sem_marks` never in X
- no `config.FORBIDDEN_FEATURES` in X
- deployment rows (target NULL) never enter any period
- validation data never influences training features
- excluded later semesters: `[7]`

## 9. Preprocessing isolation
Median imputer + per-model scaler are **fit only on the training period** and
used to transform validation (same `_preprocess_fit_transform` layer as the
single hold-forward, unit-tested for train-only fitting).

## 10. Candidate models
Only the supported M1 candidates: **ridge, hist_gbm, xgboost**. No new
algorithms, no tuning, no ensembles.

## 11. Metrics per window
| Window | Valid | Model | MAE | RMSE | R² |
|---|---|---|---|---|---|
| 1 (val 2) | 610 | ridge | 3.398 | 4.226 | 0.826 |
| | | hist_gbm | 3.375 | 4.117 | 0.835 |
| | | xgboost | 3.660 | 4.569 | 0.797 |
| 2 (val 3) | 660 | ridge | 3.392 | 4.177 | 0.825 |
| | | hist_gbm | 3.166 | 3.818 | 0.853 |
| | | xgboost | 3.215 | 3.897 | 0.847 |
| 3 (val 4) | 610 | ridge | 3.656 | 4.429 | 0.804 |
| | | hist_gbm | 3.330 | 3.985 | 0.842 |
| | | xgboost | 3.344 | 4.031 | 0.838 |
| 4 (val 5) | 400 | ridge | 3.368 | 4.112 | 0.799 |
| | | hist_gbm | 3.217 | 3.842 | 0.824 |
| | | xgboost | 3.238 | 3.928 | 0.816 |
| 5 (val 6) | 400 | ridge | 3.309 | 4.145 | 0.788 |
| | | hist_gbm | 3.073 | 3.602 | 0.840 |
| | | xgboost | 3.070 | 3.603 | 0.840 |

## 12. Aggregate temporal metrics (mean±std across 5 windows)
| Model | mean MAE | mean RMSE | mean R² |
|---|---|---|---|
| ridge | 3.424±0.134 | 4.218±0.125 | 0.808±0.017 |
| **hist_gbm** | **3.232±0.122** | **3.873±0.193** | **0.839±0.010** |
| xgboost | 3.306±0.221 | 4.006±0.353 | 0.828±0.021 |

## 13. Reproducibility result
Re-running the full sweep twice against the same data produces **identical**
window boundaries, row counts, student counts, feature columns, per-window
metrics, and aggregates (exact to 1e-12). Verified live and by unit test.

## 14. Comparison with previous single hold-out
The single hold-out was window 5 (train 1–5 → valid 6): hist_gbm MAE 3.073 /
R² 0.840 — reproduced **exactly** here (hist_gbm 3.073, ridge 3.309, xgboost
3.070). The multi-holdout confirms that single point was representative rather
than a lucky spike: window-to-window hist_gbm MAE ranges 3.07–3.37 (mean 3.23,
std 0.12).

## 15. Interpretation
- **hist_gbm is the most stable**: lowest mean MAE (3.232) and the smallest
  variance of both MAE (0.122) and R² (0.010) across windows.
- xgboost is competitive on mean (3.306) but more variable (MAE std 0.221) and
  weakest on the earliest window (3.660 on valid 2).
- ridge is consistent but consistently the weakest (mean MAE 3.424).
- Using more training semesters tends to help hist_gbm (3.375 at train=1 → 3.073
  at train=1–5), indicating reasonable data scaling behavior.

## 16. Model-selection decision
Temporal sweep is **validation-only**; the existing M1 model selection
(**HistGradientBoosting**) remains **unchanged**. Although xgboost wins window 5
by a tiny margin (3.070 vs 3.073), it loses the other four windows and is more
variable, so there is no evidence to replace hist_gbm. No rule in the existing
M1 contract mandates changing selection based on this evaluation.

## 17. Limitations
- Student overlap (80/80, then 50/50) reflects the same-population temporal
  design; it does not measure generalization to wholly unseen students.
- Early windows (train 1 → valid 2) use a single training semester and are
  slightly noisier.
- Validation set sizes shrink at the later windows (400 rows), so point estimates
  are modestly uncertain.
- Small 80-student cohort; R² ≈ 0.83–0.84 should be read with that caveat.
- Semester 7 (the true deployment boundary) cannot be temporally validated (3
  labeled rows) and remains excluded.

## 18. Exact next recommended single step (REPORTED ONLY — NOT EXECUTED)
A **prediction-readiness assessment for M1**: package the selected hist_gbm
baseline (already persisted at `artifacts/models/m1_subject_endmarks.joblib`)
with a documented inference contract (feature alignment to the 12 encoded
columns, target clip to `[0,70]`) and a scoring/calibration check on the held-out
deployment rows — still **without** any production/API/dashboard integration,
and explicitly BEFORE student-facing prediction is considered.
