"""
Phase 15-23 - SECOND (CLEAN) M1 EXPERIMENT
==========================================
Trains clean-experiment models inside artifacts/clean_experiment/:

  m1_v1 = Ridge                    on A_core (clean)
  m1_v2 = HistGradientBoosting     on A_core (clean)
  m1_v3 = HistGradientBoosting     on the best of B/C/D by VALIDATION MAE
          (best feature set chosen on val ONLY; test touched once).

Split: identical student-group split as the previous experiment
(outputs/split_assignment.csv, seed 42) -> test rows are the same 10,860
records used by the old experiment, so old-vs-clean is a like-for-like
comparison.

Writes:
  artifacts/clean_experiment/m1_v{1,2,3}/...
  outputs/predictions_clean_m1_v{1,2,3}.csv
  reports/clean_ablation.json
"""

import os
import sys
import json
import pickle

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.inspection import permutation_importance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train_common import (BASE_DIR, OUT_DIR, train_model, predict, evaluate, SEED)
from create_features_clean import FEATURE_SETS, MODEL_CONFIG

ART_ROOT = os.path.join(BASE_DIR, "artifacts", "clean_experiment")
os.makedirs(ART_ROOT, exist_ok=True)

CLEAN_DATASET = os.path.join(OUT_DIR, "m1_dataset_clean.csv")
SPLIT_FILE = os.path.join(OUT_DIR, "split_assignment.csv")


def load_clean_split():
    df = pd.read_csv(CLEAN_DATASET, low_memory=False)
    df = df.dropna(subset=["end_sem_marks"]).reset_index(drop=True)
    split = pd.read_csv(SPLIT_FILE, usecols=["enrollment_record_id", "split"])
    df = df.merge(split, on="enrollment_record_id", how="left", validate="one_to_one")
    miss = df["split"].isna().sum()
    assert miss == 0, f"unassigned rows: {miss}"
    # verify same test rows as old experiment
    old_test = set(pd.read_csv(os.path.join(OUT_DIR, "split_assignment.csv"))[
        pd.read_csv(os.path.join(OUT_DIR, "split_assignment.csv"))["split"] == "test"]
        ["enrollment_record_id"])
    new_test = set(df[df["split"] == "test"]["enrollment_record_id"])
    assert old_test == new_test, "test rows differ from previous experiment!"
    return df


def compute_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    ss = float(np.sum((y_true - y_true.mean()) ** 2))
    se = float(np.sum((y_true - y_pred) ** 2))
    r2 = 1 - se / ss
    corr = float(pearsonr(y_true, y_pred)[0])
    resid = y_true - y_pred
    return {
        "n": int(len(y_true)),
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "corr": round(corr, 4),
        "within5": round(100 * np.mean(np.abs(resid) <= 5), 3),
        "within10": round(100 * np.mean(np.abs(resid) <= 10), 3),
        "within15": round(100 * np.mean(np.abs(resid) <= 15), 3),
        "actual_mean": round(float(y_true.mean()), 3),
        "actual_std": round(float(y_true.std()), 3),
        "actual_min": round(float(y_true.min()), 3),
        "actual_max": round(float(y_true.max()), 3),
        "pred_mean": round(float(y_pred.mean()), 3),
        "pred_std": round(float(y_pred.std()), 3),
        "pred_min": round(float(y_pred.min()), 3),
        "pred_max": round(float(y_pred.max()), 3),
        "resid_mean": round(float(resid.mean()), 3),
        "resid_median": round(float(np.median(resid)), 3),
        "resid_std": round(float(resid.std()), 3),
        "underpredict_pct": round(100 * (resid > 0).mean(), 3),
        "overpredict_pct": round(100 * (resid < 0).mean(), 3),
        "n_raw_below_0": int((y_pred < 0).sum()),
        "n_raw_above_70": int((y_pred > 70).sum()),
    }


def main():
    df = load_clean_split()
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]
    print(f"train={len(train_df)} val={len(val_df)} test={len(test_df)}")

    # ---- ablation: HGB on A/B/C/D, decide on VALIDATION only ----
    ablation = {}
    for name, feats in FEATURE_SETS.items():
        pipe = train_model(train_df, feats, "hist_gradient_boosting")
        p = predict(pipe, val_df, feats)
        m = compute_metrics(val_df["end_sem_marks"].values, p)
        ablation[name] = {"features": len(feats), "val_mae": m["mae"], "val_rmse": m["rmse"],
                          "val_r2": m["r2"]}
        print(f"ablation {name}: val MAE={m['mae']} RMSE={m['rmse']} R2={m['r2']}")

    best_set = min(["B_core_history", "C_core_history_learning",
                    "D_core_history_attendance"],
                   key=lambda s: ablation[s]["val_mae"])
    ablation["best_set"] = best_set
    with open(os.path.join(BASE_DIR, "reports", "clean_ablation.json"), "w", encoding="utf-8") as fh:
        json.dump(ablation, fh, indent=2)
    print(f"BEST feature set by VAL MAE: {best_set}")

    # ---- final configs ----
    MODEL_CONFIG["m1_v3"]["feature_set"] = best_set
    configs = {
        "m1_v1": dict(MODEL_CONFIG["m1_v1"]),
        "m1_v2": dict(MODEL_CONFIG["m1_v2"]),
        "m1_v3": dict(MODEL_CONFIG["m1_v3"]),
    }

    all_out = {}
    for NAME, cfg in configs.items():
        feats = FEATURE_SETS[cfg["feature_set"]]
        mtype = cfg["model"]
        print(f"\nTraining clean {NAME}: {mtype} / {cfg['feature_set']} ({len(feats)} feats)")

        pipe = train_model(train_df, feats, mtype)
        art_dir = os.path.join(ART_ROOT, NAME)
        os.makedirs(art_dir, exist_ok=True)

        all_pred = {}
        for split_name, d in [("train", train_df), ("val", val_df), ("test", test_df)]:
            p = predict(pipe, d, feats)
            d = d.copy()
            d["prediction"] = p
            d[["enrollment_record_id", "student_id", "subject_id", "semester_no",
               "end_sem_marks", "prediction"]].to_csv(
                os.path.join(art_dir, f"predictions_{split_name}.csv"), index=False)
            preds = d[["enrollment_record_id", "student_id", "subject_id",
                       "semester_no", "end_sem_marks", "prediction"]]
            all_pred[split_name] = preds

        results = {"name": NAME, "model": mtype, "feature_set": cfg["feature_set"],
                   "features": feats, "n_features": len(feats),
                   "test_rows": len(test_df), "seed": SEED}
        test_pred = predict(pipe, test_df, feats)
        test_true = test_df["end_sem_marks"].values
        results["val"] = compute_metrics(val_df["end_sem_marks"].values, predict(pipe, val_df, feats))
        results["test"] = compute_metrics(test_true, test_pred)
        results["test"]["n_clipped"] = int(np.sum((np.clip(test_pred, 0, 70) != test_pred)))

        if NAME == "m1_v3":
            try:
                sample = val_df.sample(n=min(4000, len(val_df)), random_state=SEED)
                pi = permutation_importance(pipe, sample[feats], sample["end_sem_marks"].values,
                                            n_repeats=5, random_state=SEED,
                                            scoring="neg_mean_absolute_error")
                imp = pd.DataFrame({
                    "feature": feats,
                    "importance_mean": pi.importances_mean,
                    "importance_std": pi.importances_std,
                }).sort_values("importance_mean", ascending=False)
                results["feature_importance"] = imp[["feature", "importance_mean"]].to_dict("records")
                imp.to_csv(os.path.join(art_dir, "feature_importance.csv"), index=False)
            except Exception as e:
                print("permutation importance skipped:", e)

        with open(os.path.join(art_dir, "model.pkl"), "wb") as fh:
            pickle.dump(pipe, fh)
        with open(os.path.join(art_dir, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
        with open(os.path.join(art_dir, "features.json"), "w", encoding="utf-8") as fh:
            json.dump({"features": feats, "model_type": mtype, "feature_set": cfg["feature_set"],
                       "seed": SEED}, fh, indent=2)

        all_pred["test"].to_csv(os.path.join(OUT_DIR, f"predictions_clean_{NAME}.csv"), index=False)
        all_out[NAME] = results
        print(f"  {NAME} TEST: MAE={results['test']['mae']} RMSE={results['test']['rmse']} "
              f"R2={results['test']['r2']} corr={results['test']['corr']}")

    summary_path = os.path.join(ART_ROOT, "all_metrics.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(all_out, fh, indent=2)
    print("\nSaved summary ->", summary_path)


if __name__ == "__main__":
    main()