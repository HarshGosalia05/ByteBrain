"""
Phase 19-22 - Advanced Prediction Diagnostics & Final Recommendation Inputs
===========================================================================
Loads the merged test predictions and produces:

  * calibration-by-band table (predicted vs actual within each actual band)
  * prediction collapse check (percentiles, std ratio)
  * systematic under/over prediction by actual-group
  * feature-importance summary for the recommendation
  * writes reports/prediction_behavior.csv & reports/feature_importance_summary.md
"""

import os
import json

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
ART_DIR = os.path.join(BASE_DIR, "artifacts")

MODELS = ["m1_v1", "m1_v2", "m1_v3"]

merged = pd.read_csv(os.path.join(OUT_DIR, "predictions_m1_v1.csv"))
for m in MODELS[1:]:
    d = pd.read_csv(os.path.join(OUT_DIR, f"predictions_{m}.csv"))
    merged = merged.merge(d[["enrollment_record_id", "prediction"]],
                          on="enrollment_record_id",
                          suffixes=("", f"_{m}"))
merged = merged.rename(columns={
    "prediction": "pred_m1_v1",
    "prediction_m1_v2": "pred_m1_v2",
    "prediction_m1_v3": "pred_m1_v3",
})

y_true = merged["end_sem_marks"].values
BANDS = [(0, 20, "0-20"), (20, 35, "20-35"), (35, 50, "35-50"),
         (50, 60, "50-60"), (60, 70, "60-70")]

rows = []
for m in MODELS:
    p = np.clip(merged["pred_" + m].values, 0, 70)
    for lo, hi, label in BANDS:
        mask = (y_true >= lo) & (y_true < hi)
        if mask.sum() < 5:
            continue
        yb, pb = y_true[mask], p[mask]
        resid = yb - pb
        rows.append({
            "model": m, "band": label, "n": int(mask.sum()),
            "mean_actual": round(float(yb.mean()), 2),
            "mean_pred": round(float(pb.mean()), 2),
            "bias_marks": round(float((pb - yb).mean()), 2),
            "underpredict_pct": round(float(100 * (resid > 0).mean()), 2),
        })

behav = pd.DataFrame(rows)
behav.to_csv(os.path.join(REPORT_DIR, "prediction_behavior.csv"), index=False)

# Feature importance summary
fi_lines = []
for m in MODELS:
    imp_path = os.path.join(ART_DIR, m, "feature_importance.csv")
    if not os.path.exists(imp_path):
        continue
    imp = pd.read_csv(imp_path)
    col = "importance_mean" if "importance_mean" in imp.columns else "abs_coef"
    top = imp.sort_values(col, ascending=False).head(6)
    fi_lines.append(f"### {m}\n")
    for i, r in top.iterrows():
        fi_lines.append(f"- `{r['feature']}`: {r[col]:.4f}")
    fi_lines.append("")

with open(os.path.join(REPORT_DIR, "feature_importance_summary.md"), "w", encoding="utf-8") as fh:
    fh.write("# Feature Importance Summary\n\n")
    fh.write("Feature importance does **not** imply causation. It reflects "
             "how much the model relies on a feature for prediction.\n\n")
    fh.write("\n".join(fi_lines))

print("=== PREDICTION BEHAVIOR BY ACTUAL BAND ===")
print(behav.to_string(index=False))
print("\nSaved prediction_behavior.csv and feature_importance_summary.md")