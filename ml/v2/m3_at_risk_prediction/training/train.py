"""M3 v2 — Main Training Script: At-Risk Student Prediction (binary).

Usage:
    cd d:/KenexAi/ByteBrain/ml
    python -m v2.m3_at_risk_prediction.training.train

Phases:
    1. Load data from Supabase (read-only)
    2. Integrity checks
    3. Build feature matrix (T -> T+1, point-in-time) + at-risk label
    4. Select features + define transitions
    5. Class imbalance analysis
    6. Baselines (majority class, prior-backlog rule) on temporal holdout
    7. GroupKFold model selection (all algorithms)
    8. Threshold selection on GROUP-VALIDATION probabilities (not holdout)
    9. Temporal hold-forward validation (hold out T=6 -> predict sem 7)
    10. Select best algorithm by evidence (F1 positive + PR-AUC)
    11. Fit final model on all training transitions, with chosen threshold
    12. Save artifact (with threshold, target def, metrics, fingerprint)
    13. Reload + verification
    14. Write report

No synthetic oversampling. class_weight='balanced' only. Threshold tuned on
validation data; the temporal holdout is NEVER used for tuning.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from .. import config
from ..data.loader import SupabaseLoader
from ..features.builder import build_feature_matrix, check_joins, dataset_provenance, fingerprint
from ..features.leakage_gate import run_leakage_gate
from ..preprocessing.pipeline import M3Preprocessor, select_features
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
    pre = M3Preprocessor(strategy="median")
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
    """Select the best algorithm on CV evidence (never the temporal holdout).

    Primary metric: cross-validated F1 of the positive (at-risk) class — the
    standard balanced metric for an imbalanced classifier. Tie-break by CV
    PR-AUC, then ROC-AUC, then model simplicity (interpretability). Recall is
    constrained by the threshold step (recall >= 0.5 with a precision floor) and
    reported explicitly; it is not traded off here against the balanced F1.
    """
    def key_fn(a):
        r = cv_results[a]
        f1 = r.metric_mean("f1")
        if f1 != f1 or f1 is None:      # NaN guard (fold with no positives)
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
        "# M3 v2 — At-Risk Student Prediction: Validation Report",
        "",
        f"- **Model:** `{md['model_name']}` v{md['model_version']}",
        f"- **Trained:** {md['trained_at']}",
        f"- **Cohort:** {md['cohort']}",
        f"- **Target:** {md['target']}",
        f"- **Target definition:** {md['target_definition']}",
        f"- **Training transitions:** T = {md['training_transitions']} -> T+1 in {{2..7}}",
        f"- **Temporal holdout:** T = {md['temporal_holdout_transition']} -> predict semester 7",
        f"- **Selected algorithm:** {best_algo}",
        f"- **Decision threshold:** {md['threshold']:.3f}",
        f"- **Feature count:** {md['n_features']}",
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
    L += ["", "---", "", "## 2. Class Balance (Phase G)", "",
          f"- Total transitions: {class_balance['total']:,}",
          f"- Positive (at-risk): {class_balance['positive']:,} ({class_balance['positive_rate']:.2f}%)",
          f"- Negative: {class_balance['negative']:,}",
          f"- Distinct at-risk students: {class_balance['positive_students']:,}",
          f"- Positive rate by T: {class_balance['rate_by_semester']}",
          "- Imbalance handled via `class_weight='balanced'` (no synthetic oversampling).", "",
          "---", "", "## 3. Baselines (temporal holdout, T=6 -> sem 7)", "",
          "| Baseline | Recall | Precision | F1 | PR-AUC | ROC-AUC |",
          "|---|---|---|---|---|---|"]
    for name in ["majority_class", "prior_backlog_rule"]:
        m = baselines[name]["_metrics_clf_like"]
        L.append(f"| {name} | {m['recall']:.3f} | {m['precision']:.3f} | {m['f1']:.3f} | {m['pr_auc']:.3f} | {m['roc_auc']:.3f} |")

    L += ["", "---", "", "## 4. GroupKFold CV (5-fold × 3 seeds, grouped by student)", "",
          "| Algorithm | F1 | Recall | Precision | ROC-AUC | PR-AUC | BalAcc | Positive Folds |",
          "|---|---|---|---|---|---|---|---|"]
    for algo, r in cv_results.items():
        s = r.summary()
        L.append(f"| {algo} | {s['f1_mean']:.3f} | {s['recall_mean']:.3f} | {s['precision_mean']:.3f} | "
                 f"{s['roc_auc_mean']:.3f} | {s['pr_auc_mean']:.3f} | {s['balanced_accuracy_mean']:.3f} | {s['positive_informative_folds']}/{s['n_folds']} |")

    L += ["", "---", "", "## 5. Threshold Selection (on group CV, NOT holdout)", "",
          f"- Selected threshold: **{threshold['threshold']:.3f}**",
          f"- Validation F1: {threshold['f1']:.3f} | Recall: {threshold['recall']:.3f} | Precision: {threshold['precision']:.3f} | Specificity: {threshold['specificity']:.3f}",
          f"- Tuning constraints: recall >= {config.THRESHOLD_TARGET_RECALL}, precision >= {config.THRESHOLD_MIN_PRECISION} (config knobs).", "",
          "---", "", "## 6. Temporal Hold-Forward Validation (hold out T=6)", "",
          f"- Training transitions: {temporal.training_transitions}",
          f"- Holdout transition: {temporal.holdout_transition}",
          f"- Training rows: {temporal.n_train:,} | Holdout rows: {temporal.n_val:,}",
          f"- Training students: {temporal.n_train_students:,} | Holdout students: {temporal.n_val_students:,}",
          f"- Student overlap: {temporal.student_overlap:,} (same cohort, later semester — expected)", ""]
    for algo, m in temporal.by_algorithm.items():
        mm = m["threshold_0_5"]
        L.append(f"| {algo} | 0.5 | {mm['recall']:.3f} | {mm['precision']:.3f} | {mm['f1']:.3f} | "
                 f"{mm['roc_auc']:.3f} | {mm['pr_auc']:.3f} | {mm['balanced_accuracy']:.3f} |")

    L += ["", "---", "", "## 7. Selected Model on Holdout (with chosen threshold)",
          f"- Algorithm: {best_algo} | Threshold: {md['threshold']:.3f}", ""]
    ho = temporal.by_algorithm[best_algo]["threshold_0_5"]
    L.append(f"- (0.5-threshold holdout) Recall: {ho['recall']:.3f} | Precision: {ho['precision']:.3f} | "
             f"F1: {ho['f1']:.3f} | ROC-AUC: {ho['roc_auc']:.3f} | PR-AUC: {ho['pr_auc']:.3f}")

    L += ["", "---", "", "## 8. Leakage Check", "",
          f"- Forbidden T+1/future/placement features verified absent: **{md['leakage_check']['pass']}**",
          f"- Forbidden features found: {md['leakage_check']['forbidden_found'] or 'NONE'}",
          "- Current-T outcome columns are legitimate features (T complete); T+1 outcome columns are forbidden.",
          "- The M1/M2 v2 forbidden lists were NOT reused; the M3-specific T+1 list is applied.", "",
          "---", "", "## 9. Feature List", "", "```"]
    for i, feat in enumerate(artifact["feature_names"]):
        L.append(f"  {i+1:3d}. {feat}")
    L += ["```", "", "---", "", "## 10. Artifact Information", "",
          f"- **File:** `{config.MODEL_FILE}`",
          f"- **Reload test:** {md['reload_test']}",
          f"- **Prediction test:** {md['prediction_test']}",
          f"- **Dataset fingerprint:** {provenance['fingerprints'].get('semester_summary', 'N/A')}",
          f"- **Target definition:** {md['target_definition']}", "",
          "---", "", "## 11. Limitations", "",
          "1. Same division (CSE 6A); may not generalize to other departments without retraining.",
          "2. The temporal holdout is the same cohort one semester later — a fully unseen cohort is not available.",
          "3. ~2.8% positive class: recall of the at-risk class is prioritized but F1/pr thresholds constrain over-flagging.",
          "4. All 1,200 students are at semester 8 (final/internship). They have NO valid T+1, so the live endpoint returns NO_DATA for them; it serves earlier-semester students / future cohorts.",
          "5. Predicted risk probabilities are ESTIMATES, not certainties.",
    ]
    report_file = config.REPORT_DIR / "m3_v2_validation_report.md"
    report_file.write_text("\n".join(L), encoding="utf-8")
    print(f"  Report saved: {report_file}")


def main() -> None:
    t0 = time.time()
    print("=" * 70)
    print("M3 v2 — At-Risk Student Prediction Training")
    print("=" * 70)

    tables = SupabaseLoader.load_sync()
    provenance = dataset_provenance(tables)

    print("\n[Phase 2] Integrity checks...")
    integrity = check_joins(tables)
    print(f"  All integrity checks: {'PASS' if integrity['pass'] else 'FAIL'}")

    print("\n[Phase 3] Building feature matrix (T -> T+1)...")
    fact = build_feature_matrix(tables)
    print(f"  Feature matrix: {len(fact):,} rows")

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
        raise ValueError(f"M3 LEAKAGE DETECTED: {forbidden_found}")
    X_full_leak = select_features(fact_6a)
    gate = run_leakage_gate(X_full_leak, required_targets=config.TARGETS)
    print(f"  Leakage gate (fail-closed): PASS — scanned {gate['columns_checked']} feature columns")

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
            for t in config.TRAINING_TRANSITIONS
        },
    }
    print(f"  Positive: {pos:,} / {len(y_all):,} = {class_balance['positive_rate']:.2f}% "
          f"({class_balance['positive_students']} students)")

    print("\n[Phase 6] Baselines (temporal holdout)...")
    baselines = {
        "majority_class": baseline_majority_class(holdout_fact[config.TARGET_AT_RISK].astype(int)),
        "prior_backlog_rule": baseline_prior_backlog_rule(holdout_fact),
    }
    for name, b in baselines.items():
        m = b["_metrics_clf_like"]
        print(f"  {name}: recall={m['recall']:.3f} F1={m['f1']:.3f} PR-AUC={m['pr_auc']:.3f}")

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
                  f"PR-AUC={s['pr_auc_mean']:.3f} ROC-AUC={s['roc_auc_mean']:.3f}")
        except Exception as e:
            print(f"  {algo:22s} SKIPPED ({e})")
    if not cv_results:
        raise RuntimeError("No algorithm succeeded in CV")

    best_algo = select_best_algorithm(cv_results)
    print(f"\n  Selected algorithm (CV F1/PR-AUC): {best_algo}")

    # ── Phase 8: Threshold selection on GROUP-VALIDATION probabilities ───────
    # Aggregate held-out (validation) probabilities from GroupKFold for the
    # chosen algorithm, train the model fold-per-fold, collect probas on the
    # held-out slices, then pick a threshold. Never on the temporal holdout.
    print("\n[Phase 8] Threshold selection (on group CV probabilities)...")
    cv_probas = []
    cv_true = []
    for seed in range(config.N_SEEDS):
        from sklearn.model_selection import GroupKFold as GKF
        gkf = GKF(n_splits=config.N_FOLDS)
        for _, (tr_idx, va_idx) in enumerate(gkf.split(X_train, y_tr, groups_train)):
            X_tr_, X_va_ = X_train.iloc[tr_idx].copy(), X_train.iloc[va_idx].copy()
            y_tr_, y_va_ = y_tr.iloc[tr_idx], y_tr.iloc[va_idx]
            pre = M3Preprocessor(strategy="median")
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
    print(f"  Threshold: {threshold['threshold']:.3f} (F1={threshold['f1']:.3f}, "
          f"recall={threshold['recall']:.3f}, precision={threshold['precision']:.3f})")

    print("\n[Phase 9] Temporal hold-forward validation (T=6 -> sem 7)...")
    temporal = run_temporal_holdout(
        fact=fact_6a, X_full=select_features(fact_6a),
        training_transitions=train_transitions, holdout_transition=holdout_transition,
        algorithms=config.MODEL_ALGORITHMS, seed=config.RANDOM_STATE)
    for algo, m in temporal.by_algorithm.items():
        mm = m["threshold_0_5"]
        print(f"  {algo:22s} holdout recall={mm['recall']:.3f} precision={mm['precision']:.3f} "
              f"F1={mm['f1']:.3f} PR-AUC={mm['pr_auc']:.3f}")

    print("\n[Phase 10] Fit final model on ALL training transitions...")
    final_fact = fact_6a[fact_6a["semester_no"].isin(config.TRAINING_TRANSITIONS)].copy()
    X_final = select_features(final_fact)
    X_final = X_final.reindex(columns=feature_names, fill_value=0)
    y_final = final_fact[config.TARGET_AT_RISK].astype(int)
    pre_final, scaler_final, model_final = fit_final_model(X_final, y_final, best_algo)

    print("\n[Phase 11] Saving artifact...")
    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": model_final,
        "preprocessor": pre_final,
        "scaler": scaler_final,                 # None unless logistic_regression
        "threshold": threshold["threshold"],
        "feature_names": feature_names,
        "target": config.TARGET_AT_RISK,
        "target_bounds": None,                  # binary classification
        "metadata": {
            "model_name": config.MODEL_NAME,
            "model_version": config.MODEL_VERSION,
            "algorithm": best_algo,
            "target": config.TARGET_AT_RISK,
            "target_definition": (
                "is_at_risk_next_sem = 1 if semester_result(T+1) in {'FAIL','ATKT'} "
                "OR backlog_count(T+1) > 0 else 0"
            ),
            "cohort": "CSE_6A_1200",
            "student_prefix": config.COHORT_ID_PREFIX,
            "training_transitions": config.TRAINING_TRANSITIONS,
            "temporal_holdout_transition": config.TEMPORAL_HOLDOUT_TRANSITION,
            "valid_observation_semesters": config.VALID_OBSERVATION_SEMESTERS,
            "max_academic_semester": config.MAX_ACADEMIC_SEMESTER,
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
                "training_transitions": temporal.training_transitions,
                "holdout_transition": temporal.holdout_transition,
                "n_train": temporal.n_train,
                "n_val": temporal.n_val,
                "by_algorithm": {a: {"threshold_0_5": m["threshold_0_5"]}
                                 for a, m in temporal.by_algorithm.items()},
            },
            "baselines": {k: v["_metrics_clf_like"] for k, v in baselines.items()},
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
    print("  Reload: PASS | Prediction: PASS (20 samples, probs in [0,1])")

    artifact["metadata"]["reload_test"] = "PASS"
    artifact["metadata"]["prediction_test"] = "PASS"

    print("\n[Phase 13] Writing validation report...")
    write_report(artifact, cv_results, temporal, baselines, class_balance,
                 provenance, threshold, best_algo)

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"M3 v2 TRAINING COMPLETE in {elapsed:.1f}s")
    print(f"  Artifact: {config.MODEL_FILE}")
    print(f"  Algorithm: {best_algo} | Threshold: {threshold['threshold']:.3f}")
    print(f"  Leakage: {'PASS' if leakage_check['pass'] else 'FAIL'}")
    print(f"  Reload: PASS  |  Prediction: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()