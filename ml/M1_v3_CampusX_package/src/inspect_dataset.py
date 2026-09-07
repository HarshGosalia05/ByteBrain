"""
Phase 1 - Dataset Inspection
============================
Inspects ALL CSV files in the supabase export folder and produces a
comprehensive inventory report (dataset_inventory.md).

This script does NOT modify any original CSV file.
"""

import os
import sys
import glob
import json
import traceback
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Source CSVs live here (do not move/copy into model_training).
# Fall back to default name if present in project root.
_DEFAULT_DATA = os.path.join(os.path.dirname(BASE_DIR), "supabase_export_04_09_latest_27table")
if os.path.isdir(_DEFAULT_DATA):
    DATA_DIR = _DEFAULT_DATA
else:
    DATA_DIR = os.path.join(BASE_DIR, "supabase_export_04_09_latest_27table")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "dataset_inventory.md")

os.makedirs(REPORT_DIR, exist_ok=True)


def load_csv(path):
    """Load a CSV trying a few delimiters/encodings."""
    if path.endswith(".csv"):
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(path, encoding=enc)
            except Exception:
                continue
    for sep in (",", "|", ";", "\t"):
        try:
            return pd.read_csv(path, sep=sep)
        except Exception:
            continue
    raise ValueError(f"Cannot read {path}")


def summarize_numeric(col):
    """Return a short string summarizing a numeric column."""
    try:
        return {
            "min": round(float(col.min()), 3),
            "max": round(float(col.max()), 3),
            "mean": round(float(col.mean()), 3),
            "nulls": int(col.isna().sum()),
        }
    except Exception:
        return None


def inspect_one(name, path):
    info = {"file": name, "path": path, "size_bytes": os.path.getsize(path)}
    try:
        raw = load_csv(path)
    except Exception as e:
        info["error"] = f"{e}\n{traceback.format_exc()}"
        return info

    df = raw.copy()
    info["rows"] = int(len(df))
    info["cols"] = int(df.shape[1])
    info["columns"] = list(df.columns)
    info["dtypes"] = {c: str(df[c].dtype) for c in df.columns}
    info["missing"] = {c: int(df[c].isna().sum()) for c in df.columns}
    info["missing_pct"] = {c: round(float(df[c].isna().mean() * 100), 2) for c in df.columns}
    info["duplicate_rows"] = int(df.duplicated().sum())

    # candidate ID columns
    id_likes = [c for c in df.columns if any(
        k in c.lower() for k in ("student_id", "subject_id", "user_id", "_id", "id=", "enrollment_id")
    )]
    for c in id_likes:
        try:
            info.setdefault("unique_ids", {})[c] = int(df[c].nunique())
        except Exception:
            pass

    # candidate student_id
    for c in df.columns:
        if c.lower() in ("student_id", "studentid"):
            try:
                info["student_id_col"] = c
                info["unique_student_ids"] = int(df[c].nunique())
            except Exception:
                pass
    for c in df.columns:
        if c.lower() in ("subject_id", "subjectid"):
            try:
                info["subject_id_col"] = c
                info["unique_subject_ids"] = int(df[c].nunique())
            except Exception:
                pass

    # numeric column summary
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    info["numeric_summary"] = {}
    for c in num_cols:
        info["numeric_summary"][c] = summarize_numeric(df[c])

    return info


def main():
    # Read the data folder
    if not os.path.isdir(DATA_DIR):
        print(f"Data directory not found: {DATA_DIR}")
        sys.exit(1)

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    results = []
    for f in files:
        name = os.path.basename(f)
        print(f"Inspecting {name} ...")
        results.append(inspect_one(name, f))

    # Write markdown report
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("# Dataset Inventory\n\n")
        fh.write(f"Export folder: `{DATA_DIR}`\n\n")
        fh.write(f"Total CSV files: {len(results)}\n\n")
        fh.write("## Summary Table\n\n")
        fh.write("| File | Rows | Cols | Dup Rows | Unique Students | Unique Subjects |\n")
        fh.write("|------|------|------|----------|-----------------|-----------------|\n")
        for r in results:
            if "error" in r:
                fh.write(f"| {r['file']} | ERROR | | | | |\n")
                continue
            us = r.get("unique_student_ids", "-")
            su = r.get("unique_subject_ids", "-")
            fh.write(
                f"| {r['file']} | {r['rows']} | {r['cols']} | "
                f"{r['duplicate_rows']} | {us} | {su} |\n"
            )

        fh.write("\n## Per-File Detail\n")
        for r in results:
            fh.write(f"\n### {r['file']}\n\n")
            if "error" in r:
                fh.write(f"ERROR reading file:\n\n```\n{r['error']}\n```\n")
                continue
            fh.write(f"- Rows: {r['rows']}\n")
            fh.write(f"- Columns: {r['cols']}\n")
            fh.write(f"- Duplicate rows: {r['duplicate_rows']}\n")
            if r.get("student_id_col"):
                fh.write(f"- Student ID col: `{r['student_id_col']}` (unique: {r['unique_student_ids']})\n")
            if r.get("subject_id_col"):
                fh.write(f"- Subject ID col: `{r['subject_id_col']}` (unique: {r['unique_subject_ids']})\n")
            fh.write("\n#### Columns & Data Types\n\n")
            fh.write("| Column | Type | Missing | Missing% |\n")
            fh.write("|--------|------|---------|----------|\n")
            for c in r["columns"]:
                fh.write(
                    f"| {c} | {r['dtypes'][c]} | {r['missing'][c]} | "
                    f"{r['missing_pct'][c]} |\n"
                )
            if r.get("numeric_summary"):
                fh.write("\n#### Numeric Columns Summary\n\n")
                fh.write("| Column | Min | Max | Mean | Nulls |\n")
                fh.write("|--------|-----|-----|------|-------|\n")
                for c, s in r["numeric_summary"].items():
                    if s:
                        fh.write(f"| {c} | {s['min']} | {s['max']} | {s['mean']} | {s['nulls']} |\n")
            fh.write("\n---\n")

    # Also save raw JSON for downstream use
    json_path = os.path.join(REPORT_DIR, "dataset_inventory.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, default=str)

    print(f"\nWrote {REPORT_PATH}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
