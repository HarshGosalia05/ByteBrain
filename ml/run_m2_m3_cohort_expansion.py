"""M2/M3 Multi-Department (CSE + BBA) Cohort Expansion — guided run.

Re-expands the M2 regression and M3 classification training/evaluation
cohort from the CSE-only scope to the full supported multi-department cohort
(CSE + BBA) using the existing project data/feature architecture:

  - Cohort dataset built by features.v1_cohort_dataset.build_cohort_v1_dataset
    (reuses m2.data.load_tables() CSV snapshot == live DB mirror; per-student
    deployment boundary, NOT fixed at 7).
  - M2: features.v1_m2_regression.run_m2_regression (existing candidates,
    metrics, selection rule), then persists the selected multi-target artifact
    via train_and_persist_m2 (existing M2 persistence contract).
  - M3: features.v1_m3_experiment.run_m3_experiment (existing candidates,
    class_weight='balanced', GroupKFold(5) by student). Evaluation-only.

This is READ-ONLY WRT the database: no ETL, schema, API, dashboard, GenAI,
M1/M4 changes.  Only the M2 artifact + report are written by the explicit
persistence contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from features import (  # noqa: E402
    V1CohortScope,
    build_cohort_v1_dataset,
    report_cohort,
    run_m2_regression,
    m2_regression_report,
    train_and_persist_m2,
    run_m3_experiment,
    experiment_report,
)


def main():
    print("Building full multi-department (CSE + BBA) cohort dataset ...")
    dataset = build_cohort_v1_dataset(V1CohortScope())
    print(report_cohort(dataset))

    print("\n### M2 regression — expanded cohort")
    m2 = run_m2_regression(dataset)
    print(m2_regression_report(m2))

    print("\n### M3 classification — expanded cohort")
    m3 = run_m3_experiment(dataset)
    print(experiment_report(m3))

    print("\n### Persist M2 artifact (existing M2 persistence contract)")
    result, model_file, reload_pass, pred_pass = train_and_persist_m2(dataset)
    print(f"  artifact: {model_file}")
    print(f"  reload: {reload_pass} | prediction on deployment slice: {pred_pass}")


if __name__ == "__main__":
    main()
