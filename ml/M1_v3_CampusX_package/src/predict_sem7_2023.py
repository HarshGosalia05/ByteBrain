"""
Add Sem 7 forward predictions for the 2023 batch (50 students actually in
semester 7) to the UI dataset.

Grain asked for by the user:
  ONE ROW PER STUDENT  (50 rows)
  value = mean of each model's predicted end_sem_marks (0-70) across the
          student's 7 semester-7 subjects.

The trained pipelines are applied as-is (including internal missing-value
imputation), so no data is fabricated. Pre-end-sem assessment / weekly
learning data for these rows were not exported, so the models fall back on
internal marks, mid-sem marks and (for m1_v3) historical context.

Writes:
  outputs/sem7_2023_predictions.csv        per student-subject detail
  outputs/sem7_2023_student_summary.csv    per student (50 rows)
  ui/predictions_all.json                  appended with 50 marked rows
"""

import os
import json
import pickle

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
UI_DIR = os.path.join(BASE_DIR, "ui")
SRC_DIR = os.path.join(os.path.dirname(BASE_DIR),
                       "supabase_export_04_09_latest_27table")

MODELS = ["m1_v1", "m1_v2", "m1_v3"]

ds = pd.read_csv(os.path.join(OUT_DIR, "m1_dataset.csv"), low_memory=False)

# 2023 batch = the 80 students in attendance.csv (all admitted 2023)
att = pd.read_csv(os.path.join(SRC_DIR, "attendance.csv"))
legacy = set(att["student_id"])

sem7 = ds[(ds["student_id"].isin(legacy)) & (ds["semester_no"] == 7)].copy()
print(f"Sem 7 rows: {len(sem7)} | students: {sem7['student_id'].nunique()}")

def load_model(m):
    with open(os.path.join(BASE_DIR, "artifacts", m, "model.pkl"), "rb") as fh:
        pipe = pickle.load(fh)
    feats = json.load(open(os.path.join(BASE_DIR, "artifacts", m,
                                        "features.json")))["features"]
    return pipe, feats

preds = {}
for m in MODELS:
    pipe, feats = load_model(m)
    X = sem7[feats]
    p = np.clip(pipe.predict(X), 0, 70)
    sem7["pred_" + m] = p
    preds[m] = p

# ---- per student-subject detail ----
detail_cols = (["student_id", "enrollment_record_id", "subject_id",
                "subject_code", "semester_no", "internal_marks",
                "mid_sem_marks"]
               + ["pred_" + m for m in MODELS])
detail = sem7.merge(
    pd.read_csv(os.path.join(SRC_DIR, "student_subject_enrollment.csv"),
                usecols=["enrollment_record_id", "subject_name"],
                low_memory=False).drop_duplicates("enrollment_record_id"),
    on="enrollment_record_id", how="left")
detail[detail_cols + ["subject_name"]].to_csv(
    os.path.join(OUT_DIR, "sem7_2023_predictions.csv"), index=False)

# ---- per student summary (mean across the 7 subjects) ----
stu = pd.read_csv(os.path.join(SRC_DIR, "students.csv"))
stu = stu[["student_id", "enrollment_no", "first_name", "last_name",
           "admission_year"]]
stu["student_name"] = stu["first_name"].fillna("") + " " + stu["last_name"].fillna("")

summary = (sem7.groupby("student_id")
           .agg({**{"pred_" + m: "mean" for m in MODELS},
                 "internal_marks": "mean", "mid_sem_marks": "mean"})
           .round(2).reset_index())
summary = summary.merge(stu[["student_id", "student_name", "enrollment_no",
                             "admission_year"]], on="student_id", how="left")
summary.to_csv(os.path.join(OUT_DIR, "sem7_2023_student_summary.csv"),
               index=False)
print(f"Student summary rows: {len(summary)}")
print(summary[["student_id", "student_name", "pred_m1_v1", "pred_m1_v2",
               "pred_m1_v3"]].head(10).to_string(index=False))

# ---- append to UI json (marked) ----
ui_json = os.path.join(UI_DIR, "predictions_all.json")
existing = json.load(open(ui_json, encoding="utf-8"))
print(f"existing UI rows: {len(existing)}")

forward_rows = []
for _, r in summary.iterrows():
    forward_rows.append({
        "row_type": "forward_sem7_2023",
        "enrollment_record_id": None,
        "student_id": r["student_id"],
        "student_name": r["student_name"],
        "enrollment_no": r["enrollment_no"] if not pd.isna(r["enrollment_no"]) else None,
        "subject_id": None,
        "subject_code": "SEM7AVG",
        "subject_name": "Sem 7 Average (2023 batch)",
        "semester_no": 7,
        "department_name": "CSE",
        "credits": None,
        "subject_type": None,
        "internal_marks": r["internal_marks"],
        "mid_sem_marks": r["mid_sem_marks"],
        "end_sem_marks": None,   # not yet known -> forward prediction
        "m1_v1": r["pred_m1_v1"],
        "m1_v2": r["pred_m1_v2"],
        "m1_v3": r["pred_m1_v3"],
        "err_m1_v1": None,
        "err_m1_v2": None,
        "err_m1_v3": None,
        "aerr_m1_v1": None,
        "aerr_m1_v2": None,
        "aerr_m1_v3": None,
    })

# tag existing rows
for row in existing:
    row.setdefault("row_type", "test")

all_rows = existing + forward_rows
with open(ui_json, "w", encoding="utf-8") as fh:
    json.dump(all_rows, fh)
print(f"Wrote {ui_json}: {len(all_rows)} rows ({len(forward_rows)} forward)")