"""
Supplementary: Feature-set ablation for the final recommendation.
Trains HistGradientBoosting on feature sets B, C, D using the SAME split and
reports test metrics. This lets us state whether learning activity (C) or
attendance trend (D) materially improves over Core+History (B).

Does not replace the primary v1/v2/v3 models.
"""
import os
import json

import numpy as np
import pandas as pd

from create_features import FEATURE_SETS
from train_common import (BASE_DIR, load_dataset, train_model, predict)

df = load_dataset()
train_df = df[df["split"] == "train"]
test_df = df[df["split"] == "test"]

results = {}
for name in ["B_core_history", "C_core_history_learning",
             "D_core_history_attendance"]:
    feats = FEATURE_SETS[name]
    pipe = train_model(train_df, feats, "hist_gradient_boosting")
    p = predict(pipe, test_df, feats)
    y = test_df["end_sem_marks"].values
    mae = float(np.mean(np.abs(y - p)))
    rmse = float(np.sqrt(np.mean((y - p) ** 2)))
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot
    results[name] = {"mae": round(mae, 4), "rmse": round(rmse, 4),
                     "r2": round(r2, 4), "features": len(feats)}
    print(f"{name}: MAE={mae:.4f} RMSE={rmse:.4f} R2={r2:.4f} ({len(feats)} feats)")

with open(os.path.join(BASE_DIR, "reports", "ablation_results.json"), "w",
          encoding="utf-8") as fh:
    json.dump(results, fh, indent=2)
print("\nSaved ablation_results.json")