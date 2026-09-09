"""M3 v3 — Main Training Script: Same-Semester End-Term Risk Prediction.

Usage:
    cd ml
    python -m v3.m3_endterm_risk.training.train

Phases:
    1. Load data from Supabase (read-only)
    2. Integrity checks
    3. Build feature matrix (mid-sem only, same-semester label)
    4. Select features + define splits
    5. Class imbalance analysis
    6. Baselines on temporal holdout
    7. GroupKFold model selection
    8. Threshold selection on group CV probabilities
    9. Temporal hold-forward validation (hold out T=7)
    10. Select best algorithm
    11. Fit final model
    12. Save artifact
    13. Reload + verification
    14. Write report
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from .. import config
from ..data.loader import load_training_data
from ..features.builder import build_feature_matrix, check_joins, dataset_provenance, fingerprint
from ..features.leakage_gate import run_leakage_gate
from ..preprocessing.pipeline import M3V3Preprocessor, select_features
from ..validation.cv import (
    CVResult,
    TemporalResult,
    baseline_majority_class,
    baseline_prior_backlog_rule,
    make_model,
    run_group_kfold_cv,
    run_temporal_holdout,
    select_threshold,
)


def fit_final_model(X: pd.DataFrame, y: pd.Series, algorithm: str,
                    seed: int = config.RANDOM_STATE):
    """Fit the final classifier. Returns (preprocessor, scaler_or_None, model)."""
    pre = M3V3Preprocessor(strategy="median")
    X_proc = pre.fit_transform(X)
    scaler = None
    if algorithm == "logistic_regression":
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler().fit(X_proc)
        X_proc = scaler.transform(X_proc)
    model = make_model(algorithm, seed)
    model.fit(X_proc, y)
    return pre, scaler, model


def select_best_algorithm(cv_results: dict[str, CVResult]) -> str:
    """Select best algorithm by CV F1 (positive class)."""
    def key_fn(a):
        r = cv_results[a]
        f1 = r.metric_mean("f1")
        if f1 != f1 or f1 is None:
            f1 = -1.0
        prauc = r.metric_mean("pr_auc")
        if prauc != prauc or prauc is None:
            prauc = -1.0
        roc = r.metric_mean("roc_auc")
        if roc != roc or roc is None:
            roc = -1.0
        simplicity = {
            "logistic_regression": 0, "hist_gbm": 1,
            "random_forest": 2, "xgboost": 3,
        }.get(a, 4)
        return (-f1, -prauc, -roc, simplicity)

    return min(cv_results.keys(), key=key_fn)


def write_report(artifact: dict, cv_results: dict[str, CVResult],
                 temporal: TemporalResult, baselines: dict,
                 class_balance: dict, provenance: dict,
                 threshold: dict, best_algo: str) -> None:
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md = artifact["metadata"]
    L = [
        "# M3 v3 — Same-Semester End-Term Risk Prediction: Validation Report",
        "",
        f"- **Model:** `{md['model_name']}` v{md['model_version']}",
        f"- **Trained:** {md['trained_at']}",
        f"- **Cohort:** {md['cohort']}",
        f"- **Target:** {md['target']}",
        f"- **Target definition:** {md['target_definition']}",
        f"- **Task:** Same-semester Mid-Sem → End-Term Risk",
        f"- **Training semesters:** T = {md['training_semesters']}",
        f"- **Temporal holdout:** T = {md['temporal_holdout_semester']}",
        f"- **Selected algorithm:** {best_algo}",
        f"- **Decision threshold:** {md['threshold']:.3f}",
        f"- **Feature count:** {md['n_features']}",
        f"- **Prediction point:** {config.PREDICTION_POINT}",
        "",
        "---", "",
        "## 1. Dataset Provenance", "",
        "| Table | Row Count |", "|---|---|",
    ]
    for tbl, cnt in provenance["row_counts"].items():
        L.append(f"| {tbl} | {cnt:,} |")
    L += ["", "---", "", "## 2. Class Balance", "",
          f"- Total transitions: {class_balance['total']:,}",
          f"- Positive (at-risk): {class_balance['positive']:,} ({class_balance['positive_rate']:.2f}%)",
          f"- Negative: {class_balance['negative']:,}",
          f"- Distinct at-risk students: {class_balance['positive_students']:,}",
          "- Imbalance handled via `class_weight='balanced'`.", "",
          "---", "", "## 3. Baselines (temporal holdout)", "",
          "| Baseline | Recall | Precision | F1 | PR-AUC | ROC-AUC |",
          "|---|---|---|---|---|---|"]
    for name in ["majority_class", "prior_backlog_rule"]:
        m = baselines[name]["_metrics_clf_like"]
        L.append(f"| {name} | {m['recall']:.3f} | {m['precision']:.3f} | {m['f1']:.3f} | {m['pr_auc']:.3f} | {m['roc_auc']:.3f} |")

    L += ["", "---", "", "## 4. GroupKFold CV", "",
          "| Algorithm | F1 | Recall | Precision | ROC-AUC | PR-AUC | BalAcc |",
          "|---|---|---|---|---|---|---|"]
    for algo, r in cv_results.items():
        s = r.summary()
        L.append(f"| {algo} | {s['f1_mean']:.3f} | {s['recall_mean']:.3f} | {s['precision_mean']:.3f} | "
                 f"{s['roc_auc_mean']:.3f} | {s['pr_auc_mean']:.3f} | {s['balanced_accuracy_mean']:.3f} |")

    L += ["", "---", "", "## 5. Threshold Selection", "",
          f"- Selected threshold: **{threshold['threshold']:.3f}**",
          f"- F1: {threshold['f1']:.3f} | Recall: {threshold['recall']:.3f} | Precision: {threshold['precision']:.3f}", "",
          "---", "", "## 6. Temporal Hold-Forward Validation", "",
          f"- Training semesters: {temporal.training_semesters}",
          f"- Holdout semester: {temporal.holdout_semester}",
          f"- Training rows: {temporal.n_train:,} | Holdout rows: {temporal.n_val:,}", ""]

    for algo, m in temporal.by_algorithm.items():
        mm = m["threshold_0_5"]
        L.append(f"| {algo} | {mm['recall']:.3f} | {mm['precision']:.3f} | {mm['f1']:.3f} | "
                 f"{mm['roc_auc']:.3f} | {mm['pr_auc']:.3f} | {mm['balanced_accuracy']:.3f} |")

    L += ["", "---", "", "## 7. Feature List", "", "```"]
    for i, feat in enumerate(artifact["feature_names"]):
        L.append(f"  {i+1:3d}. {feat}")
    L += ["```", "", "---", "", "## 8. Leakage Check", "",
          f"- End-semester forbidden features verified absent: **{md['leakage_check']['pass']}**",
          "- No end-sem marks, SGPA, percentage, or result in feature matrix.", "",
          "---", "", "## 9. Artifact", "",
          f"- **File:** `{config.MODEL_FILE}`",
          f"- **Reload test:** {md['reload_test']}",
          f"- **Prediction test:** {md['prediction_test']}", ""]

    report_file = config.REPORT_DIR / "m3_v3_validation_report.md"
    report_file.write_text("\n".join(L), encoding="utf-8")
    print(f"  Report saved: {report_file}")


def main() -> None:
    t0 = time.time()
    print("=" * 70)
    print("M3 v3 — Same-Semester End-Term Risk Prediction Training")
    print("=" * 70)

    import asyncpg
    from urllib.parse import quote_plus
    from pathlib import Path

    env = Path("C:/Users/HET SHAH/ByteBrain/.env.local").read_text()
    env_dict = {}
    for line in env.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env_dict[k.strip()] = v.strip().strip('"').strip("'")

    dsn = (
        f"postgresql://{env_dict['DB_USER']}:{quote_plus(env_dict['DB_PASSWORD'])}"
        f"@{env_dict['DB_HOST']}:{env_dict['DB_PORT']}/{env_dict['DB_NAME']}"
    )

    async def _load():
        conn = await asyncpg.connect(dsn, statement_cache_size=0)
        try:
            return await load_training_data(conn)
        finally:
            await conn.close()

    tables = asyncio.run(_load())
    provenance = dataset_provenance(tables)

    print("\n[Phase 2] Integrity checks...")
    integrity = check_joins(tables)
    print(f"  All integrity checks: {'PASS' if integrity['pass'] else 'FAIL'}")

    print("\n[Phase 3] Building feature matrix (same-semester)...")
    fact = build_feature_matrix(tables)
    print(f"  Feature matrix: {len(fact):,} rows")

    print("\n[Phase 4] Selecting features and splitting...")
    fact_6a = fact[fact["student_id"].str.startswith(config.COHORT_ID_PREFIX)].copy()

    train_sems = [s for s in config.TRAINING_SEMESTERS if s != config.TEMPORAL_HOLDOUT_SEMESTER]
    holdout_sem = config.TEMPORAL_HOLDOUT_SEMESTER
    train_fact = fact_6a[fact_6a["semester_no"].isin(train_sems)].copy()
    holdout_fact = fact_6a[fact_6a["semester_no"] == holdout_sem].copy()
    print(f"  Training semesters T={train_sems}: {len(train_fact):,} rows")
    print(f"  Temporal holdout T={holdout_sem}: {len(holdout_fact):,} rows")

    X_train = select_features(train_fact)
    groups_train = train_fact["student_id"]
    X_holdout = select_features(holdout_fact).reindex(columns=X_train.columns, fill_value=0)

    feature_names = list(X_train.columns)
    forbidden_found = [c for c in config.FORBIDDEN_FEATURES if c in feature_names] \
        + [t for t in config.TARGETS if t in feature_names]
    leakage_check = {"pass": len(forbidden_found) == 0, "forbidden_found": forbidden_found}
    print(f"  Leakage check: {'PASS' if leakage_check['pass'] else 'FAIL — ' + str(forbidden_found)}")
    if not leakage_check["pass"]:
        raise ValueError(f"M3 v3 LEAKAGE DETECTED: {forbidden_found}")

    X_full_leak = select_features(fact_6a)
    gate = run_leakage_gate(X_full_leak, required_targets=config.TARGETS)
    print(f"  Leakage gate: PASS — scanned {gate['columns_checked']} columns")

    print("\n[Phase 5] Class imbalance analysis...")
    y_all = fact_6a[config.TARGET_AT_RISK].astype(int)
    pos = int(y_all.sum())
    class_balance = {
        "total": int(len(y_all)),
        "positive": pos,
        "negative": int(len(y_all) - pos),
        "positive_rate": 100.0 * pos / len(y_all),
        "positive_students": int(fact_6a.loc[y_all == 1, "student_id"].nunique()),
        "rate_by_semester": {
            int(t): float(100.0 * y_all[fact_6a["semester_no"] == t].sum()
                          / (fact_6a["semester_no"] == t).sum())
            for t in config.TRAINING_SEMESTERS
        },
    }
    print(f"  Positive: {pos:,} / {len(y_all):,} = {class_balance['positive_rate']:.2f}%")

    print("\n[Phase 6] Baselines (temporal holdout)...")
    baselines = {
        "majority_class": baseline_majority_class(holdout_fact[config.TARGET_AT_RISK].astype(int)),
        "prior_backlog_rule": baseline_prior_backlog_rule(holdout_fact),
    }
    for name, b in baselines.items():
        m = b["_metrics_clf_like"]
        print(f"  {name}: recall={m['recall']:.3f} F1={m['f1']:.3f}")

    print("\n[Phase 7] GroupKFold model selection...")
    cv_results: dict[str, CVResult] = {}
    y_tr = train_fact[config.TARGET_AT_RISK].astype(int)
    for algo in config.MODEL_ALGORITHMS:
        try:
            cv = run_group_kfold_cv(X_train, y_tr, groups_train, algorithm=algo,
                                    n_folds=config.N_FOLDS, seeds=list(range(config.N_SEEDS)))
            cv_results[algo] = cv
            s = cv.summary()
            print(f"  {algo:22s} F1={s['f1_mean']:.3f} recall={s['recall_mean']:.3f} "
                  f"PR-AUC={s['pr_auc_mean']:.3f}")
        except Exception as e:
            print(f"  {algo:22s} SKIPPED ({e})")
    if not cv_results:
        raise RuntimeError("No algorithm succeeded in CV")

    best_algo = select_best_algorithm(cv_results)
    print(f"\n  Selected algorithm: {best_algo}")

    print("\n[Phase 8] Threshold selection...")
    cv_probas = []
    cv_true = []
    for seed in range(config.N_SEEDS):
        from sklearn.model_selection import GroupKFold as GKF
        gkf = GKF(n_splits=config.N_FOLDS)
        for _, (tr_idx, va_idx) in enumerate(gkf.split(X_train, y_tr, groups_train)):
            X_tr_, X_va_ = X_train.iloc[tr_idx].copy(), X_train.iloc[va_idx].copy()
            y_tr_, y_va_ = y_tr.iloc[tr_idx], y_tr.iloc[va_idx]
            pre = M3V3Preprocessor(strategy="median")
            X_tr_proc = pre.fit_transform(X_tr_)
            X_va_proc = pre.transform(X_va_)
            if best_algo == "logistic_regression":
                from sklearn.preprocessing import StandardScaler
                sc = StandardScaler().fit(X_tr_proc)
                X_tr_proc = sc.transform(X_tr_proc)
                X_va_proc = sc.transform(X_va_proc)
            m = make_model(best_algo, seed)
            m.fit(X_tr_proc, y_tr_)
            cv_probas.extend(m.predict_proba(X_va_proc)[:, 1].tolist())
            cv_true.extend(y_va_.tolist())
    threshold = select_threshold(np.array(cv_true), np.array(cv_probas))
    print(f"  Threshold: {threshold['threshold']:.3f} (F1={threshold['f1']:.3f})")

    print("\n[Phase 9] Temporal hold-forward validation...")
    temporal = run_temporal_holdout(
        fact=fact_6a, X_full=select_features(fact_6a),
        training_semesters=train_sems, holdout_semester=holdout_sem,
        algorithms=config.MODEL_ALGORITHMS, seed=config.RANDOM_STATE)
    for algo, m in temporal.by_algorithm.items():
        mm = m["threshold_0_5"]
        print(f"  {algo:22s} holdout recall={mm['recall']:.3f} F1={mm['f1']:.3f}")

    print("\n[Phase 10] Fit final model...")
    final_fact = fact_6a.copy()
    X_final = select_features(final_fact)
    X_final = X_final.reindex(columns=feature_names, fill_value=0)
    y_final = final_fact[config.TARGET_AT_RISK].astype(int)
    pre_final, scaler_final, model_final = fit_final_model(X_final, y_final, best_algo)

    print("\n[Phase 11] Saving artifact...")
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": model_final,
        "preprocessor": pre_final,
        "scaler": scaler_final,
        "threshold": threshold["threshold"],
        "feature_names": feature_names,
        "target": config.TARGET_AT_RISK,
        "target_bounds": None,
        "metadata": {
            "model_name": config.MODEL_NAME,
            "model_version": config.MODEL_VERSION,
            "algorithm": best_algo,
            "target": config.TARGET_AT_RISK,
            "target_definition": (
                "is_at_risk_end_sem = 1 if semester_result(T) in {'FAIL','ATKT'} "
                "OR backlog_count(T) > 0 else 0"
            ),
            "task": "same_semester_midsem_to_endterm",
            "cohort": "CSE_6A_1200",
            "student_prefix": config.COHORT_ID_PREFIX,
            "training_semesters": config.TRAINING_SEMESTERS,
            "temporal_holdout_semester": config.TEMPORAL_HOLDOUT_SEMESTER,
            "prediction_point": config.PREDICTION_POINT,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "n_train_rows": int(len(train_fact)),
            "n_temporal_holdout_rows": int(len(holdout_fact)),
            "n_final_train_rows": int(len(final_fact)),
            "n_features": len(feature_names),
            "threshold": threshold["threshold"],
            "threshold_metrics": {k: float(v) for k, v in threshold.items()},
            "class_balance": {k: (float(v) if isinstance(v, float) else v)
                              for k, v in class_balance.items()},
            "leakage_check": leakage_check,
            "cv_summary": {a: r.summary() for a, r in cv_results.items()},
            "temporal_summary": {
                "training_semesters": temporal.training_semesters,
                "holdout_semester": temporal.holdout_semester,
                "n_train": temporal.n_train,
                "n_val": temporal.n_val,
                "by_algorithm": {a: {"threshold_0_5": m["threshold_0_5"]}
                                 for a, m in temporal.by_algorithm.items()},
            },
            "baselines": {k: v["_metrics_clf_like"] for k, v in baselines.items()},
            "reload_test": "PENDING",
            "prediction_test": "PENDING",
            "feature_schema_version": "v3.0",
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

    print("\n[Phase 12] Reload + prediction test...")
    loaded = joblib.load(config.MODEL_FILE)
    X_test_sample = X_holdout.head(20)
    X_test_proc = loaded["preprocessor"].transform(X_test_sample)
    if loaded["scaler"] is not None:
        X_test_proc = loaded["scaler"].transform(X_test_proc)
    probas = loaded["model"].predict_proba(X_test_proc)[:, 1]
    assert len(probas) == 20
    assert all(0.0 <= p <= 1.0 for p in probas)
    loaded["metadata"]["reload_test"] = "PASS"
    loaded["metadata"]["prediction_test"] = "PASS"
    joblib.dump(loaded, config.MODEL_FILE)
    print("  Reload: PASS | Prediction: PASS")

    artifact["metadata"]["reload_test"] = "PASS"
    artifact["metadata"]["prediction_test"] = "PASS"

    print("\n[Phase 13] Writing report...")
    write_report(artifact, cv_results, temporal, baselines, class_balance,
                 provenance, threshold, best_algo)

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"M3 v3 TRAINING COMPLETE in {elapsed:.1f}s")
    print(f"  Artifact: {config.MODEL_FILE}")
    print(f"  Algorithm: {best_algo} | Threshold: {threshold['threshold']:.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
