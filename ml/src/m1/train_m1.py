"""M1 - Subject Performance Predictor (train_m1.py)

Baseline-first, two-stage design:
  Stage A: clean baseline using only pre-end-semester signals + safe metadata.
  Stage B: controlled historical-feature ablation ONLY if baseline is
           genuinely insufficient. OFF by default.

Outputs:
  ml/artifacts/models/m1_subject_endmarks.joblib  (single artifact)
  ml/reports/m1_report.md                          (training report)

Run:
  python -m m1.train_m1   (from ml/)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from . import config, data, evaluate

ALGOS = config.MODEL_ALGORITHMS


def encode(train: pd.DataFrame, deploy: pd.DataFrame,
           raw_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One-hot encode both frames with columns aligned to the training order."""
    X_tr = data.one_hot_encode(train, raw_cols)
    X_de = data.one_hot_encode(deploy, raw_cols)
    X_de = X_de.reindex(columns=X_tr.columns, fill_value=0)
    return X_tr, X_de


def select_algorithm(X: pd.DataFrame, y: pd.Series, groups: pd.Series) -> dict:
    results = {}
    for algo in ALGOS:
        res = evaluate.run_model_eval(X, y, groups, algo, n_seeds=config.N_SEEDS)
        results[algo] = res["summary"]
    best = min(ALGOS, key=lambda a: (results[a]["mae_mean"], results[a]["rmse_mean"]))
    return {"results": results, "best": best}


def fit_final(algorithm: str, X: pd.DataFrame, y: pd.Series):
    """Fit the final model on all training rows; returns (preprocess, model)."""
    pre = []
    if X.isna().any().any():
        imp = SimpleImputer(strategy="median").fit(X)
        pre.append({"type": "imputer", "obj": imp})
        X = pd.DataFrame(imp.transform(X), columns=X.columns)
    if algorithm == "ridge":
        scaler = StandardScaler().fit(X)
        pre.append({"type": "scaler", "obj": scaler})
        X = scaler.transform(X)
    _, model = evaluate.make_model(algorithm, config.RANDOM_STATE)
    model.fit(X, y)
    return pre, model


def apply_preprocess(pre: list[dict], X: pd.DataFrame) -> np.ndarray:
    for p in pre:
        X = p["obj"].transform(X)
    return np.asarray(X)


def verify_no_leakage(feature_names: list[str]) -> dict:
    forbidden_hit = [f for f in feature_names if f in config.FORBIDDEN_FEATURES]
    return {"forbidden_found": forbidden_hit, "ok": len(forbidden_hit) == 0}


def main() -> None:
    t0 = time.time()
    print("M1 - Subject Performance Predictor (baseline-first)")
    print("ML ROOT:", config.ML_ROOT)

    # ---- Load + join (grain: student + subject + semester; 1:1 joins, no multiplication)
    train, deploy = data.build_dataset(include_ablation=False)
    print(f"training rows (end_sem_marks NOT NULL): {len(train)}")
    print(f"deployment rows (end_sem_marks NULL):   {len(deploy)}")
    assert len(train) == 3293, f"unexpected training row count: {len(train)}"

    y = train[config.TARGET]
    groups = train["student_id"]
    X_tr, X_de = encode(train, deploy, config.BASELINE_RAW_FEATURES)
    baseline_columns = list(X_tr.columns)

    # ---- Stage A: baseline CV across algorithms
    print("\n=== STAGE A: BASELINE (pre-end signals + safe metadata only) ===")
    selection = select_algorithm(X_tr, y, groups)
    for algo in ALGOS:
        s = selection["results"][algo]
        print(f"  {algo:9s} MAE {s['mae_mean']:.3f}±{s['mae_std']:.3f}  "
              f"RMSE {s['rmse_mean']:.3f}±{s['rmse_std']:.3f}  R2 {s['r2_mean']:.4f}±{s['r2_std']:.4f}")
    best_algo = selection["best"]
    best_summary = selection["results"][best_algo]
    print(f"\n  selected algorithm: {best_algo}")

    folds = evaluate.run_cv(X_tr, y, groups, best_algo, seed=0)
    print("  per-fold (seed 0):")
    for f in folds:
        print(f"    fold {f['fold']}: MAE {f['mae']:.3f}  RMSE {f['rmse']:.3f}  R2 {f['r2']:.4f}  n={f['n_test']}")

    sufficient = evaluate.baseline_sufficient(best_summary)
    print(f"\n  baseline sufficient? {'YES' if sufficient else 'NO'} "
          f"(threshold MAE<={config.BASELINE_INSUFFICIENT_MAE}, R2>={config.BASELINE_INSUFFICIENT_R2})")

    # ---- Stage B: controlled ablation ONLY if baseline insufficient
    stage_b = {"required": not sufficient, "evaluated": False, "accepted": [], "steps": []}
    X_final_tr, X_final_de, final_columns = X_tr, X_de, list(baseline_columns)

    if not sufficient:
        print("\n=== STAGE B: controlled historical-feature ablation ===")
        train_a, deploy_a = data.build_dataset(include_ablation=True)
        raw_all = config.BASELINE_RAW_FEATURES + config.ABLATION_RAW_FEATURES
        Xa_tr, Xa_de = encode(train_a, deploy_a, raw_all)
        ya, groups_a = train_a[config.TARGET], train_a["student_id"]

        ablation = evaluate.ablation_greedy(Xa_tr, ya, groups_a, best_algo,
                                            baseline_columns, config.ABLATION_RAW_FEATURES,
                                            best_summary, folds)
        stage_b["evaluated"] = True
        stage_b["accepted"] = ablation["accepted"]
        stage_b["steps"] = ablation["steps"]
        for step in ablation["steps"]:
            print(f"  {step['feature']:22s} delta_MAE {step['delta_mae']:+.3f}  "
                  f"delta_RMSE {step['delta_rmse']:+.3f}  folds_improved {step['folds_improved']}/5  "
                  f"accepted={step['accepted']}")
        if ablation["accepted"]:
            final_columns = list(baseline_columns) + list(ablation["accepted"])
            X_final_tr, X_final_de = Xa_tr[final_columns], Xa_de[final_columns]
            stage_b["final_summary"] = ablation["final_summary"]
    else:
        print("\n=== STAGE B skipped: baseline is sufficient. No historical features added. ===")

    # ---- Final model on all training data
    pre, model = fit_final(best_algo, X_final_tr, y)
    print(f"\nFinal model: {best_algo} | features: {len(final_columns)}")

    # ---- Save artifact
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    leak_check = verify_no_leakage(final_columns)
    artifact = {
        "model": model,
        "preprocess": pre,
        "feature_names": final_columns,
        "feature_tier": {
            "baseline_raw": list(config.BASELINE_RAW_FEATURES),
            "ablation_raw": list(config.ABLATION_RAW_FEATURES),
            "accepted_ablation_raw": list(stage_b["accepted"]),
        },
        "metadata": {
            "model": "m1_subject_endmarks",
            "version": 1,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "algorithm": best_algo,
            "target": config.TARGET,
            "prediction_point": "during semester T after internal/mid/attendance recorded, before end-exam",
            "n_train_rows": int(len(train)),
            "n_deploy_rows": int(len(deploy)),
            "n_features": len(final_columns),
            "leakage_check": leak_check,
            "stage_a": {"results": {a: s for a, s in selection["results"].items()},
                        "best": best_algo,
                        "baseline_sufficient": sufficient},
            "stage_b": stage_b,
            "thresholds": {"baseline_insufficient_mae": config.BASELINE_INSUFFICIENT_MAE,
                           "baseline_insufficient_r2": config.BASELINE_INSUFFICIENT_R2,
                           "ablation_min_mae_delta": config.ABLATION_MIN_MAE_DELTA,
                           "ablation_min_rmse_delta": config.ABLATION_MIN_RMSE_DELTA,
                           "ablation_min_folds_improved": config.ABLATION_MIN_FOLDS_IMPROVED},
        },
    }
    joblib.dump(artifact, config.MODEL_FILE)
    print(f"\nArtifact saved: {config.MODEL_FILE}")

    # ---- Reload artifact and run a real prediction test on deployment rows
    reloaded = joblib.load(config.MODEL_FILE)
    X_de_final = X_final_de.reindex(columns=reloaded["feature_names"], fill_value=0)
    preds = np.clip(reloaded["model"].predict(apply_preprocess(reloaded["preprocess"], X_de_final)),
                    config.TARGET_MIN, config.TARGET_MAX)
    print("\n=== PREDICTION TEST (deployment rows - end_sem_marks currently NULL) ===")
    sample = deploy.head(10).copy()
    sample["predicted_end_sem_marks"] = np.round(preds[:10], 1)
    print(sample[["student_id", "semester_no", "subject_id", "internal_marks",
                  "mid_sem_marks", "attendance_percentage", "predicted_end_sem_marks"]].to_string(index=False))
    print(f"\npredicted distribution over {len(preds)} deployment rows: "
          f"min {preds.min():.1f}  mean {preds.mean():.1f}  max {preds.max():.1f}")

    # ---- Final verification of saved artifact feature list
    saved_features = reloaded["feature_names"]
    print("\n=== ARTIFACT VERIFICATION ===")
    print("feature count:", len(saved_features))
    print("features:", saved_features)
    print("forbidden/leakage columns found:", reloaded["metadata"]["leakage_check"]["forbidden_found"] or "NONE")
    print("leakage check OK:", reloaded["metadata"]["leakage_check"]["ok"])
    print("Stage B required:", reloaded["metadata"]["stage_b"]["required"],
          "| accepted ablation features:", reloaded["metadata"]["stage_b"]["accepted"] or "NONE")

    # ---- Write report
    _write_report(artifact, folds)
    print(f"\nReport saved: {config.REPORT_FILE}")
    print(f"Total elapsed: {time.time() - t0:.1f}s")
    print("\nM1 COMPLETE - stopped. M2 not started.")


def _write_report(artifact: dict, folds: list[dict]) -> None:
    md = artifact["metadata"]
    lines = [
        "# M1 - Subject Performance Predictor: Training Report",
        "",
        f"- Model: `{md['model']}` v{md['version']}",
        f"- Trained: {md['trained_at']}",
        f"- Target: `{md['target']}` (clip [{config.TARGET_MIN}, {config.TARGET_MAX}])",
        f"- Training rows: {md['n_train_rows']} | Deployment rows: {md['n_deploy_rows']}",
        f"- Prediction point: {md['prediction_point']}",
        "",
        "## Stage A - Baseline CV (GroupKFold(5) by student, 3 seeds)",
        "",
        "| Algorithm | MAE (mean±std) | RMSE (mean±std) | R² (mean±std) |",
        "|---|---|---|---|",
    ]
    for algo, s in md["stage_a"]["results"].items():
        lines.append(f"| {algo} | {s['mae_mean']:.3f}±{s['mae_std']:.3f} | "
                     f"{s['rmse_mean']:.3f}±{s['rmse_std']:.3f} | {s['r2_mean']:.4f}±{s['r2_std']:.4f} |")
    lines += ["", f"Selected algorithm: **{md['stage_a']['best']}**", "",
              "Per-fold (selected algorithm, seed 0):", "",
              "| Fold | MAE | RMSE | R² | n |", "|---|---|---|---|---|"]
    for f in folds:
        lines.append(f"| {f['fold']} | {f['mae']:.3f} | {f['rmse']:.3f} | {f['r2']:.4f} | {f['n_test']} |")
    lines += ["", "## Stage B decision", ""]
    lines.append(f"- Baseline sufficient: **{md['stage_a']['baseline_sufficient']}** "
                 f"(threshold MAE<={md['thresholds']['baseline_insufficient_mae']} and "
                 f"R²>={md['thresholds']['baseline_insufficient_r2']})")
    lines.append(f"- Stage B required: **{md['stage_b']['required']}**")
    if md["stage_b"]["evaluated"]:
        lines += ["", "| Candidate | ΔMAE | ΔRMSE | folds improved | accepted |", "|---|---|---|---|---|"]
        for step in md["stage_b"]["steps"]:
            lines.append(f"| {step['feature']} | {step['delta_mae']:+.3f} | "
                         f"{step['delta_rmse']:+.3f} | {step['folds_improved']}/5 | {step['accepted']} |")
    lines.append(f"- Accepted historical features: **{md['stage_b']['accepted'] or 'NONE'}**")
    lines += ["", "## Final model", "",
              f"- Algorithm: `{md['algorithm']}` | Features: {md['n_features']}",
              f"- Leakage check: {md['leakage_check']['ok']} "
              f"({md['leakage_check']['forbidden_found'] or 'no forbidden columns'})",
              "", "## Feature list", ""]
    lines += ["```"]
    lines += [f"  {i+1:2d}. {f}" for i, f in enumerate(artifact["feature_names"])]
    lines += ["```"]
    config.REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
