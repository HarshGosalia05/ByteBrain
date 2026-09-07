"""
Shared HGB training driver used by m1_v2 and m1_v3.
"""
import os
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from create_features import FEATURE_SETS, MODEL_CONFIG
from train_common import (BASE_DIR, load_dataset, train_model, predict,
                          evaluate, SEED)


def run(NAME):
    ART_DIR = os.path.join(BASE_DIR, "artifacts", NAME)
    os.makedirs(ART_DIR, exist_ok=True)

    CFG = MODEL_CONFIG[NAME]
    FEATURES = FEATURE_SETS[CFG["feature_set"]]
    MODEL_TYPE = CFG["model"]

    df = load_dataset()
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]

    print(f"Training {NAME} | model={MODEL_TYPE} | feature_set={CFG['feature_set']} "
          f"({len(FEATURES)} features)")
    print(f"train={len(train_df)} val={len(val_df)} test={len(test_df)}")

    pipe = train_model(train_df, FEATURES, MODEL_TYPE)

    for split_name, d in [("train", train_df), ("val", val_df), ("test", test_df)]:
        d = d.copy()
        d["prediction"] = predict(pipe, d, FEATURES)
        d[["enrollment_record_id", "student_id", "subject_id", "semester_no",
           "end_sem_marks", "prediction"]].to_csv(
            os.path.join(ART_DIR, f"predictions_{split_name}.csv"), index=False)

    results = {"name": NAME, "model": MODEL_TYPE, "feature_set": CFG["feature_set"],
               "features": FEATURES}
    for split_name, d in [("val", val_df), ("test", test_df)]:
        p = predict(pipe, d, FEATURES)
        results[split_name] = evaluate(d["end_sem_marks"].values, p)

    test_pred = predict(pipe, test_df, FEATURES)
    test_true = test_df["end_sem_marks"].values
    raw = test_pred.copy()
    clipped = np.clip(raw, 0, 70)
    n_clip = int((raw != clipped).sum())
    results["test"]["raw_pred_range"] = [float(np.min(raw)), float(np.max(raw))]
    results["test"]["clipped_pred_range"] = [float(np.min(clipped)), float(np.max(clipped))]
    results["test"]["n_clipped"] = n_clip
    results["test"]["pct_clipped"] = round(100 * n_clip / len(raw), 3)

    resid = test_true - raw
    results["test"]["resid_mean"] = round(float(np.mean(resid)), 3)
    results["test"]["resid_median"] = round(float(np.median(resid)), 3)
    results["test"]["resid_std"] = round(float(np.std(resid)), 3)
    results["test"]["underpredict_rate"] = round(100 * (resid > 0).mean(), 3)
    results["test"]["overpredict_rate"] = round(100 * (resid < 0).mean(), 3)

    try:
        sample = val_df.sample(n=min(3000, len(val_df)), random_state=SEED)
        Xs = sample[FEATURES]
        ys = sample["end_sem_marks"].values
        pi = permutation_importance(pipe, Xs, ys, n_repeats=5, random_state=SEED,
                                    scoring="neg_mean_absolute_error")
        imp = pd.DataFrame({
            "feature": FEATURES,
            "importance_mean": pi.importances_mean,
            "importance_std": pi.importances_std,
        }).sort_values("importance_mean", ascending=False)
        results["feature_importance"] = imp[["feature", "importance_mean"]].to_dict("records")
        imp.to_csv(os.path.join(ART_DIR, "feature_importance.csv"), index=False)
    except Exception as e:
        print("permutation importance skipped:", e)

    with open(os.path.join(ART_DIR, "model.pkl"), "wb") as fh:
        pickle.dump(pipe, fh)
    with open(os.path.join(ART_DIR, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    with open(os.path.join(ART_DIR, "features.json"), "w", encoding="utf-8") as fh:
        json.dump({"features": FEATURES, "model_type": MODEL_TYPE,
                   "seed": SEED}, fh, indent=2)

    print(json.dumps({"val": results["val"], "test": results["test"]}, indent=2))
    print("Saved artifacts to", ART_DIR)
    return results
