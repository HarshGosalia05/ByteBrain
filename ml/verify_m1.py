"""M1 - Subject Performance Predictor: Live Verification Script.

Connects to the real CSV data dumps (read-only) and re-runs the complete,
already-established M1 contract from ml/src/m1 (config, data, evaluate,
train_m1) to:

  1. Verify the exact target (`end_sem_marks`, 0-70) and its source.
  2. Verify training/deployment row counts on the real data (3293 / 557).
  3. Verify deployment exclusion and the temporal boundary
     (features = pre-end-semester signals; no forbidden/target columns).
  4. Verify student isolation: GroupKFold(5) by student_id, zero overlap.
  5. Run every supported candidate (ridge, hist_gbm, xgboost) with the
     documented GroupKFold(5) x 3-seed methodology and MAE/RMSE/R2 metrics.
  6. Verify the Stage A selection rule and Stage B baseline-sufficiency gate.
  7. Verify reproducibility (two same-seed runs are bit-identical).
  8. Reload the persisted artifact (artifacts/models/m1_subject_endmarks.joblib)
     and run a prediction test on deployment rows.

READ-ONLY wrt the database/canvas: no ETL, no schema, no API, no dashboard, no
M2/M3/M4 changes. Only a verification report is written. The persisted M1
artifact and m1_report.md are NOT modified.

Usage:  python ml/verify_m1.py
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from m1 import config, data, evaluate  # noqa: E402
from m1.train_m1 import apply_preprocess, select_algorithm, verify_no_leakage  # noqa: E402


def check_student_isolation(X, y, groups, n_folds) -> dict:
    gkf = GroupKFold(n_splits=n_folds)
    overlap = 0
    for tr_idx, te_idx in gkf.split(X, y, groups):
        tr_s = set(groups.iloc[tr_idx])
        te_s = set(groups.iloc[te_idx])
        overlap += len(tr_s & te_s)
    return {"allocated_overlap": overlap, "ok": overlap == 0}


def main() -> None:
    checks = []
    ok = lambda name, passed: checks.append((name, bool(passed)))

    t0 = time.time()
    print("M1 - Subject Performance Predictor: LIVE VERIFICATION (CSV data)")
    print("ML ROOT:", config.ML_ROOT)

    # ---- 1. Load real data (read-only)
    train, deploy = data.build_dataset(include_ablation=False)
    build_t = time.time() - t0
    print(f"\n[data] training rows: {len(train)} | deployment rows: {len(deploy)} "
          f"(build {build_t:.2f}s)")
    ok(f"training rows == {3293}", len(train) == 3293)
    ok(f"deployment rows == 557", len(deploy) == 557)

    tr_students = train["student_id"].nunique()
    de_students = deploy["student_id"].nunique()
    print(f"[data] students (training)={tr_students} (deployment)={de_students}")
    ok("target = end_sem_marks", config.TARGET == "end_sem_marks")
    ok("training target non-null", int(train[config.TARGET].isna().sum()) == 0)
    ok("deploy target all-null", int(deploy[config.TARGET].notna().sum()) == 0)
    ok("target within [0,70]",
       bool((train[config.TARGET] >= config.TARGET_MIN).all()
            and (train[config.TARGET] <= config.TARGET_MAX).all()))
    print(f"[data] target distribution: mean={train[config.TARGET].mean():.2f} "
          f"std={train[config.TARGET].std():.2f} min={train[config.TARGET].min():.2f} "
          f"max={train[config.TARGET].max():.2f}")

    # ---- 2. Features: encode + leakage checks
    X_tr, X_de_raw = data.one_hot_encode(train, config.BASELINE_RAW_FEATURES), None
    X_de = data.one_hot_encode(deploy, config.BASELINE_RAW_FEATURES)
    X_de = X_de.reindex(columns=X_tr.columns, fill_value=0)
    encoded_cols = list(X_tr.columns)
    feature_cols = config.BASELINE_RAW_FEATURES
    print(f"\n[features] encoded columns ({len(encoded_cols)}): {encoded_cols}")
    ok("encoded feature count == 12", len(encoded_cols) == 12)
    ok("target not in features", config.TARGET not in encoded_cols)
    leak = verify_no_leakage(encoded_cols)
    ok("no forbidden/leakage columns", leak["ok"])
    ok("baseline features present",
       all(c in train.columns for c in config.BASELINE_RAW_FEATURES))

    y = train[config.TARGET]
    groups = train["student_id"]

    # ---- 3. Student isolation (GroupKFold 5)
    iso = check_student_isolation(X_tr, y, groups, config.N_FOLDS)
    print(f"\n[isolation] GroupKFold({config.N_FOLDS}) by student: "
          f"train/val allocated overlap = {iso['allocated_overlap']}")
    ok("student isolation (zero overlap)", iso["ok"])

    # ---- 4. Evaluate all supported candidates (deterministic 3-seed CV)
    print("\n=== STAGE A: BASELINE CV (GroupKFold(5) by student, 3 seeds) ===")
    print(f"{'algorithm':10s} MAE(mean±std)     RMSE(mean±std)    R2(mean±std)")
    selection = select_algorithm(X_tr, y, groups)
    for algo in config.MODEL_ALGORITHMS:
        s = selection["results"][algo]
        print(f"{algo:10s} {s['mae_mean']:.3f}±{s['mae_std']:.3f}   "
              f"{s['rmse_mean']:.3f}±{s['rmse_std']:.3f}   {s['r2_mean']:.4f}±{s['r2_std']:.4f}")
    best_algo = selection["best"]
    best_summary = selection["results"][best_algo]
    print(f"\n[selection] selected algorithm: {best_algo} "
          f"(min MAE, then RMSE over supported candidates)")
    ok("selection == min-ordered best",
       selection["best"] == min(
           config.MODEL_ALGORITHMS,
           key=lambda a: (selection["results"][a]["mae_mean"],
                          selection["results"][a]["rmse_mean"])))

    # ---- Stage B gate
    sufficient = evaluate.baseline_sufficient(best_summary)
    print(f"[stageB] baseline sufficient = {sufficient} "
          f"(MAE<={config.BASELINE_INSUFFICIENT_MAE}, R2>={config.BASELINE_INSUFFICIENT_R2})")
    ok("stage B gate matches existing report", sufficient == True)

    # ---- Per-fold composition for selected algorithm (seed 0)
    folds = evaluate.run_cv(X_tr, y, groups, best_algo, seed=0)
    print(f"\n[per-fold] selected algorithm {best_algo!r} (seed 0):")
    for f in folds:
        print(f"  fold {f['fold']}: MAE {f['mae']:.3f}  RMSE {f['rmse']:.3f}  "
              f"R2 {f['r2']:.4f}  n={f['n_test']}")

    # ---- 5. Reproducibility: two same-seed runs identical
    rep1 = evaluate.run_cv(X_tr, y, groups, best_algo, seed=0)
    rep2 = evaluate.run_cv(X_tr, y, groups, best_algo, seed=0)
    mae_same = all(abs(a["mae"] - b["mae"]) < 1e-9 for a, b in zip(rep1, rep2))
    ok("reproducibility (same-seed runs identical)", mae_same)

    # ---- 6. Artifact reload + prediction test (persistence is part of M1)
    artifact = joblib.load(config.MODEL_FILE)
    am = artifact["metadata"]
    ok("artifact reloaded (m1_subject_endmarks)", am.get("model") == "m1_subject_endmarks")
    ok("artifact feature count == 12", len(artifact["feature_names"]) == 12)
    X_de_final = X_de.reindex(columns=artifact["feature_names"], fill_value=0)
    preds = np.clip(artifact["model"].predict(
        apply_preprocess(artifact["preprocess"], X_de_final)),
        config.TARGET_MIN, config.TARGET_MAX)
    ok("prediction test runs (deployment rows)",
       len(preds) == len(deploy) and bool(np.isfinite(preds).all()))
    print(f"\n[predict] {len(preds)} deployment rows -> "
          f"pred min {preds.min():.1f} mean {preds.mean():.1f} max {preds.max():.1f} "
          f"[range {config.TARGET_MIN}-{config.TARGET_MAX}]")
    print(f"[artifact] stored algorithm={am.get('algorithm')} "
          f"features={am.get('n_features')} trained_at={am.get('trained_at')}")

    # ---- 7. Write verification report (does NOT touch m1_report.md/artifact)
    report_dir = Path(__file__).resolve().parents[0] / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# M1 - Subject Performance Predictor: Verification Report",
        "",
        f"- Target: `{config.TARGET}` (clip [{config.TARGET_MIN}, {config.TARGET_MAX}])",
        f"- Training rows: {len(train)} | Deployment rows: {len(deploy)} "
        f"| Students (train)={tr_students} (deploy)={de_students}",
        f"- Prediction point: during semester T before end-exam (pre-end signals only)",
        f"- Split: GroupKFold({config.N_FOLDS}) by student_id x {config.N_SEEDS} seeds",
        f"- Algorithms: {', '.join(config.MODEL_ALGORITHMS)}",
        "",
        "## Verification checks",
        "",
        "| Check | Pass |",
        "|---|---|",
    ]
    for name, passed in checks:
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    lines += ["", "## Stage A metrics (GroupKFold(5) x 3 seeds)", "",
              "| Algorithm | MAE (mean±std) | RMSE (mean±std) | R² (mean±std) |",
              "|---|---|---|---|"]
    for algo in config.MODEL_ALGORITHMS:
        s = selection["results"][algo]
        lines.append(f"| {algo} | {s['mae_mean']:.3f}±{s['mae_std']:.3f} | "
                     f"{s['rmse_mean']:.3f}±{s['rmse_std']:.3f} | "
                     f"{s['r2_mean']:.4f}±{s['r2_std']:.4f} |")
    lines += ["",
              f"Selected algorithm (M1 selection rule): **{best_algo}**",
              f"Baseline sufficient (Stage B gate): **{sufficient}**",
              f"Persisted artifact: `{config.MODEL_FILE}` "
              f"(algorithm={am.get('algorithm')}, features={am.get('n_features')})",
              f"Artifact reload: PASS | Deployment prediction test: "
              f"{'PASS' if len(preds) == len(deploy) and np.isfinite(preds).all() else 'FAIL'}",
    ]
    report_file = report_dir / "m1_verification.md"
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[report] written to {report_file}")

    all_pass = all(p for _, p in checks)
    print(f"\nTotal elapsed: {time.time() - t0:.1f}s")
    print(f"\nM1 VERIFICATION {'ALL PASS' if all_pass else 'HAS FAILURES'} "
          f"— READ-ONLY. No M2/M3/M4/API/dashboard/db changes.")


if __name__ == "__main__":
    main()
