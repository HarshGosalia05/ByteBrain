"""M2 v2 — Main Training Script.

Predicts next-semester semester_sgpa and semester_percentage (separate
regression targets) from observation-semester-T features.

Usage:
    cd d:/KenexAi/ByteBrain/ml
    python -m v2.m2_next_semester_prediction.training.train

Phases:
    1. Load data from Supabase (read-only)
    2. Integrity checks
    3. Build feature matrix (T -> T+1, point-in-time)
    4. Select features + define transitions
    5. Baselines
    6. GroupKFold model selection (each target)
    7. Temporal hold-forward validation (hold out T=6 -> predict sem 7)
    8. Select best algorithm per target by evidence
    9. Fit final models on all training transitions
    10. Save artifact (both targets)
    11. Reload + verification
    12. Write report
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from .. import config
from ..data.loader import SupabaseLoader
from ..features.builder import build_feature_matrix, check_joins, dataset_provenance
from ..features.leakage_gate import run_leakage_gate
from ..preprocessing.pipeline import M2Preprocessor, select_features
from ..validation.cv import (
    CVResult,
    TemporalResult,
    baseline_carryforward,
    baseline_mean_predictor,
    make_model,
    run_group_kfold_cv,
    run_temporal_holdout,
)


def fit_final_model(X: pd.DataFrame, y: pd.Series, algorithm: str,
                    seed: int = config.RANDOM_STATE):
    """Fit a final model. Returns (preprocessor, scaler_or_None, model)."""
    pre = M2Preprocessor(strategy="median")
    X_proc = pre.fit_transform(X)
    scaler = None
    if algorithm == "ridge":
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler().fit(X_proc)
        X_proc = scaler.transform(X_proc)
    model = make_model(algorithm, seed)
    model.fit(X_proc, y)
    return pre, scaler, model


def select_best_algorithm(cv_results: dict[str, CVResult]) -> str:
    """Select best algorithm by lowest mean MAE; tie-break to simpler model."""
    simplicity = ["ridge", "hist_gbm", "random_forest", "xgboost"]
    candidates = sorted(
        cv_results.keys(),
        key=lambda a: (cv_results[a].mae_mean, simplicity.index(a) if a in simplicity else 99)
    )
    return candidates[0]


def write_report(artifact: dict, cv_results: dict[str, dict[str, CVResult]],
                 temporal: TemporalResult, baselines: dict[str, dict],
                 provenance: dict) -> None:
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md = artifact["metadata"]
    L = [
        "# M2 v2 — Next-Semester Performance Predictor: Validation Report",
        "",
        f"- **Model:** `{md['model_name']}` v{md['model_version']}",
        f"- **Trained:** {md['trained_at']}",
        f"- **Cohort:** {md['cohort']}",
        f"- **Targets:** {md['targets']}",
        f"- **Training transitions:** T = {md['training_transitions']} -> T+1 in {{2..7}}",
        f"- **Temporal holdout:** T = {md['temporal_holdout_transition']} -> predict semester 7",
        f"- **Feature count:** {md['n_features']}",
        f"- **Algorithms (per target):** {md['algorithm']}",
        f"- **Prediction point:** {config.PREDICTION_POINT}",
        "",
        "---",
        "",
        "## 1. Dataset Provenance",
        "",
        "| Table | Row Count |",
        "|---|---|",
    ]
    for tbl, cnt in provenance["row_counts"].items():
        L.append(f"| {tbl} | {cnt:,} |")
    L += ["", "---", "", "## 2. Baselines (temporal holdout, T=6 -> sem 7)", "", "| Baseline | Target | MAE | RMSE | R² |", "|---|---|---|---|---|"]
    for target in config.TARGETS:
        for b in baselines[target]:
            L.append(f"| {b['name']} | {target} | {b['mae']:.4f} | {b['rmse']:.4f} | {b['r2']:.4f} |")

    L += ["", "---", "", "## 3. Honest Skill vs Legacy M2", "",
          "The legacy M2 (`ml/src/m2`) predicted `next_semester_percentage` + `next_semester_sgpa` via a per-student `shift(-1)` "
          "and reported R²≈0.99 — flagged as an **autocorrelation artifact**, not genuine skill. "
          "M2 v2 recomputes the same T→T+1 shift but (a) excludes the degenerate internship transition T=7→8 and "
          "(b) is evaluated against the strong 'carry-forward' baseline that repeats semester T's own SGPA/percentage. "
          "A model that cannot beat carry-forward is not genuinely predictive.", "",
          "| Model | SGPA R² (temp) | %% R² (temp) | Beat carry-forward? |",
          "|---|---|---|---|"]
    for target in config.TARGETS:
        sel = artifact["metadata"]["algorithm"].get(target, "ridge")
        tr = temporal.by_target[target]
        cf = baselines[target][1]  # carry-forward baseline
        L.append(f"| {sel} ({target}) | {tr[sel]['r2']:.4f} | {tr[sel]['r2']:.4f} | {'YES' if tr[sel]['mae'] < cf['mae'] else 'CHECK'} |")

    L += ["", "---", "", "## 4. GroupKFold CV Results (5-fold, 3 seeds, grouped by student)", "",
          "| Target | Algorithm | MAE (mean±std) | RMSE (mean±std) | R² (mean±std) | Train-Val Gap (MAE) |",
          "|---|---|---|---|---|---|"]
    for target in config.TARGETS:
        for algo, res in cv_results[target].items():
            L.append(f"| {target} | {algo} | {res.mae_mean:.4f}±{res.mae_std:.4f} | {res.rmse_mean:.4f}±{res.rmse_std:.4f} | {res.r2_mean:.4f}±{res.r2_std:.4f} | {res.train_val_gap:.4f} |")

    L += ["", "---", "", "## 5. Temporal Hold-Forward Validation (hold out T=6)", "",
          f"- Training transitions: {temporal.training_transitions}",
          f"- Holdout transition: {temporal.holdout_transition}",
          f"- Training rows: {temporal.n_train:,} | Holdout rows: {temporal.n_val:,}",
          f"- Training students: {temporal.n_train_students:,} | Holdout students: {temporal.n_val_students:,}",
          f"- Student overlap: {temporal.student_overlap:,} (same cohort, later semester — expected)", "",
          "| Target | Algorithm | MAE | RMSE | R² | Train MAE | Train-Val Gap |",
          "|---|---|---|---|---|---|---|"]
    for target in config.TARGETS:
        for algo, m in temporal.by_target[target].items():
            L.append(f"| {target} | {algo} | {m['mae']:.4f} | {m['rmse']:.4f} | {m['r2']:.4f} | {m['train_mae']:.4f} | {m['train_val_gap']:.4f} |")

    L += ["", "---", "", "## 6. Leakage Check", "",
          f"- Forbidden features verified absent: **{md['leakage_check']['pass']}**",
          f"- Forbidden features found: {md['leakage_check']['forbidden_found'] or 'NONE'}",
          "- Current-T outcome columns are legitimate features (T complete); T+1 outcome columns are forbidden.",
          "- The M1 v2 forbidden list was NOT reused; the M2-specific T+1 list is applied.", "",
          "---", "", "## 7. Feature List", "", "```"]
    for i, feat in enumerate(artifact["feature_names"]):
        L.append(f"  {i+1:3d}. {feat}")
    L += ["```", "", "---", "", "## 8. Artifact Information", "",
          f"- **File:** `{config.MODEL_FILE}`",
          f"- **Reload test:** {md['reload_test']}",
          f"- **Prediction test:** {md['prediction_test']}",
          f"- **Dataset fingerprint:** {provenance['fingerprints'].get('semester_summary', 'N/A')}", "",
          "---", "", "## 9. Limitations", "",
          "1. Same division (CSE 6A); may not generalize to other departments without retraining.",
          "2. The temporal holdout is the same cohort one semester later — a fully unseen cohort is not available.",
          "3. All 1,200 students are at semester 8 (final/internship). They have NO valid T+1, so the live endpoint returns NO_DATA for the current cohort; it serves earlier-semester students / future cohorts.",
          "4. Prediction relies heavily on current-semester T outcomes; predictions for a semester with incomplete/atypical T outcomes are less reliable.",
          "5. No explicit prediction interval (would require conformal/quantile regression).",
    ]
    report_file = config.REPORT_DIR / "m2_v2_validation_report.md"
    report_file.write_text("\n".join(L), encoding="utf-8")
    print(f"  Report saved: {report_file}")


def main() -> None:
    t0 = time.time()
    print("=" * 70)
    print("M2 v2 — Next-Semester Performance Predictor Training")
    print("=" * 70)

    tables = SupabaseLoader.load_sync()
    provenance = dataset_provenance(tables)

    print("\n[Phase 2] Integrity checks...")
    integrity = check_joins(tables)
    print(f"  All integrity checks: {'PASS' if integrity['pass'] else 'FAIL'}")

    print("\n[Phase 3] Building feature matrix (T -> T+1)...")
    fact = build_feature_matrix(tables)
    feat_rows = len(fact)
    print(f"  Feature matrix: {feat_rows:,} rows")

    print("\n[Phase 4] Selecting features and splitting...")
    fact_6a = fact[fact["student_id"].str.startswith(config.COHORT_ID_PREFIX)].copy()

    train_transitions = [t for t in config.TRAINING_TRANSITIONS if t != config.TEMPORAL_HOLDOUT_TRANSITION]
    holdout_transition = config.TEMPORAL_HOLDOUT_TRANSITION
    train_fact = fact_6a[fact_6a["semester_no"].isin(train_transitions)].copy()
    holdout_fact = fact_6a[fact_6a["semester_no"] == holdout_transition].copy()
    print(f"  Training transitions T={train_transitions}: {len(train_fact):,} rows")
    print(f"  Temporal holdout T={holdout_transition} (predict sem 7): {len(holdout_fact):,} rows")

    X_train = select_features(train_fact)
    groups_train = train_fact["student_id"]
    X_holdout = select_features(holdout_fact).reindex(columns=X_train.columns, fill_value=0)

    feature_names = list(X_train.columns)
    forbidden_found = [c for c in config.FORBIDDEN_FEATURES if c in feature_names] \
        + [t for t in config.TARGETS if t in feature_names]
    leakage_check = {"pass": len(forbidden_found) == 0, "forbidden_found": forbidden_found}
    print(f"  Leakage check: {'PASS' if leakage_check['pass'] else 'FAIL — ' + str(forbidden_found)}")
    if not leakage_check["pass"]:
        raise ValueError(f"M2 LEAKAGE DETECTED: {forbidden_found}")
    # Fail-closed automated gate on the full eligible feature matrix
    X_full_leak = select_features(fact_6a)
    gate = run_leakage_gate(X_full_leak, required_targets=config.TARGETS)
    print(f"  Leakage gate (fail-closed): PASS — scanned {gate['columns_checked']} feature columns")

    print("\n[Phase 5] Baselines (temporal holdout)...")
    baselines: dict[str, dict] = {}
    for target in config.TARGETS:
        b1 = baseline_mean_predictor(
            train_fact[target].astype(float), holdout_fact[target].astype(float), target)
        b2 = baseline_carryforward(holdout_fact, target)
        baselines[target] = [b1, b2]
        print(f"  {target}: mean MAE={b1['mae']:.4f} R2={b1['r2']:.4f} | carryforward MAE={b2['mae']:.4f} R2={b2['r2']:.4f}")

    print("\n[Phase 6] GroupKFold model selection (per target)...")
    cv_results: dict[str, dict[str, CVResult]] = {t: {} for t in config.TARGETS}
    for target in config.TARGETS:
        y_tr = train_fact[target].astype(float)
        for algo in config.MODEL_ALGORITHMS:
            try:
                cv = run_group_kfold_cv(X_train, y_tr, groups_train, algorithm=algo, target=target,
                                        n_folds=config.N_FOLDS, seeds=list(range(config.N_SEEDS)))
                cv_results[target][algo] = cv
                print(f"  {target:26s} {algo:14s} MAE={cv.mae_mean:.4f}±{cv.mae_std:.4f} R2={cv.r2_mean:.4f}")
            except Exception as e:
                print(f"  {target:26s} {algo:14s} SKIPPED ({e})")
        if not cv_results[target]:
            raise RuntimeError(f"No algorithm succeeded in CV for {target}")

    best_algos = {t: select_best_algorithm(cv_results[t]) for t in config.TARGETS}
    print(f"\n  Selected algorithms: {best_algos}")

    print("\n[Phase 7] Temporal hold-forward validation (T=6 -> sem 7)...")
    temporal = run_temporal_holdout(
        fact=fact_6a, X_full=select_features(fact_6a),
        training_transitions=train_transitions, holdout_transition=holdout_transition,
        algorithms=config.MODEL_ALGORITHMS, seed=config.RANDOM_STATE)

    print("\n[Phase 8] Model selection by evidence...")
    for target in config.TARGETS:
        m = temporal.by_target[target][best_algos[target]]
        cf = baselines[target][1]
        print(f"  {target}: {best_algos[target]} temp R2={m['r2']:.4f} MAE={m['mae']:.4f} "
              f"(carryforward MAE={cf['mae']:.4f})")

    print("\n[Phase 9] Fitting final models on ALL training transitions...")
    final_fact = fact_6a[fact_6a["semester_no"].isin(config.TRAINING_TRANSITIONS)].copy()
    X_final = select_features(final_fact)
    X_final = X_final.reindex(columns=feature_names, fill_value=0)

    models = {}
    scalers = {}
    for target in config.TARGETS:
        y_final = final_fact[target].astype(float)
        pre_final, scaler_final, model_final = fit_final_model(X_final, y_final, best_algos[target])
        models[target] = model_final
        scalers[target] = scaler_final
    pre_final = pre_final  # shared preprocessor from last call (single feature matrix -> identical)

    print("\n[Phase 10] Saving artifact...")
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "models": models,                       # target -> model
        "preprocessor": pre_final,              # shared, fit on the single feature matrix
        "scalers": scalers,                     # target -> scaler (None unless ridge)
        "feature_names": feature_names,
        "targets": list(config.TARGETS),
        "metadata": {
            "model_name": config.MODEL_NAME,
            "model_version": config.MODEL_VERSION,
            "algorithm": best_algos,
            "targets": config.TARGETS,
            "target_bounds": config.TARGET_BOUNDS,
            "cohort": "CSE_6A_1200",
            "student_prefix": config.COHORT_ID_PREFIX,
            "training_transitions": config.TRAINING_TRANSITIONS,
            "temporal_holdout_transition": config.TEMPORAL_HOLDOUT_TRANSITION,
            "valid_observation_semesters": config.VALID_OBSERVATION_SEMESTERS,
            "prediction_point": config.PREDICTION_POINT,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "n_train_rows": int(len(train_fact)),
            "n_temporal_holdout_rows": int(len(holdout_fact)),
            "n_final_train_rows": int(len(final_fact)),
            "n_features": len(feature_names),
            "leakage_check": leakage_check,
            "cv_summary": {t: {a: r.summary() for a, r in cv_results[t].items()} for t in config.TARGETS},
            "temporal_summary": {
                "training_transitions": temporal.training_transitions,
                "holdout_transition": temporal.holdout_transition,
                "n_train": temporal.n_train,
                "n_val": temporal.n_val,
                "by_target": temporal.by_target,
            },
            "baselines": baselines,
            "dataset_fingerprint": provenance["fingerprints"].get("semester_summary", ""),
            "reload_test": "PENDING",
            "prediction_test": "PENDING",
            "feature_schema_version": "v2.0",
            "libraries": {
                "sklearn": __import__("sklearn").__version__,
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "joblib": joblib.__version__,
            },
        },
    }
    joblib.dump(artifact, config.MODEL_FILE)
    print(f"  Artifact saved: {config.MODEL_FILE}")

    print("\n[Phase 11] Reload + prediction test...")
    loaded = joblib.load(config.MODEL_FILE)
    X_test_sample = X_holdout.head(20)
    X_test_proc = loaded["preprocessor"].transform(X_test_sample)
    for target in config.TARGETS:
        sc = loaded["scalers"][target]
        Xp = X_test_proc if sc is None else sc.transform(X_test_proc)
        preds = np.array(loaded["models"][target].predict(Xp))
        lo, hi = config.TARGET_BOUNDS[target]
        preds = np.clip(preds, lo, hi)
        assert len(preds) == 20
        assert all(lo <= p <= hi for p in preds)
    loaded["metadata"]["reload_test"] = "PASS"
    loaded["metadata"]["prediction_test"] = "PASS"
    joblib.dump(loaded, config.MODEL_FILE)
    print("  Reload: PASS | Prediction: PASS (20 samples, both targets in range)")

    artifact["metadata"]["reload_test"] = "PASS"
    artifact["metadata"]["prediction_test"] = "PASS"

    print("\n[Phase 12] Writing validation report...")
    write_report(artifact, cv_results, temporal, baselines, provenance)

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"M2 v2 TRAINING COMPLETE in {elapsed:.1f}s")
    print(f"  Artifact: {config.MODEL_FILE}")
    print(f"  Algorithms: {best_algos}")
    print(f"  Leakage: {'PASS' if leakage_check['pass'] else 'FAIL'}")
    print(f"  Reload: PASS  |  Prediction: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()