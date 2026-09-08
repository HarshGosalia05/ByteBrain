"""Dataset and feature builder for M2-TP: Next-Semester Theory & Practical Performance Prediction.

Confined strictly to M2_TP_CampusX_package.
Enforces:
  1. Strict temporal cutoff: to predict semester S, only data from semesters < S is used.
  2. Zero fabrication: unfinalized semesters (e.g. CSE Sem 7 missing end-sem) are never used as targets.
  3. Strict subject type separation: M2_T uses historical Theory signals; M2_P uses historical Lab signals.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, List

DEFAULT_DATA_DIR = r"D:\KenexAi\ByteBrain\supabase_export_04_09_latest_27table"

SHARED_FEATURES = [
    "target_semester_no",
    "department_code",
    "gender",
    "category",
    "admission_year",
    "prev_completed_semesters",
    "prev_overall_sgpa_mean",
    "prev_overall_pct_mean",
    "prev_overall_attendance_mean",
    "prev_cumulative_backlogs",
    "latest_sem_sgpa",
    "latest_sem_pct",
    "latest_sem_attendance",
    "target_sem_total_credits",
]

THEORY_SPECIFIC_FEATURES = [
    "prev_theory_pct_mean",
    "prev_theory_pct_std",
    "prev_theory_pct_min",
    "prev_theory_pct_max",
    "latest_sem_theory_pct",
    "theory_pct_trend",
    "prev_theory_internal_avg",
    "prev_theory_midsem_avg",
    "prev_theory_assignment_avg",
    "prev_theory_quiz_avg",
    "prev_theory_submission_delay_avg",
    "prev_theory_pre_endsem_pct_avg",
    "prev_theory_count",
    "target_sem_theory_count",
    "prev_theory_sessions_sum",
    "prev_theory_resource_views_sum",
    "prev_theory_assessment_attempts_sum",
    "prev_theory_late_submission_rate",
]

PRACTICAL_SPECIFIC_FEATURES = [
    "prev_lab_pct_mean",
    "prev_lab_pct_std",
    "prev_lab_pct_min",
    "prev_lab_pct_max",
    "latest_sem_lab_pct",
    "lab_pct_trend",
    "prev_lab_internal_avg",
    "prev_lab_midsem_avg",
    "prev_lab_assignment_avg",
    "prev_lab_quiz_avg",
    "prev_lab_submission_delay_avg",
    "prev_lab_pre_endsem_pct_avg",
    "prev_lab_count",
    "has_prior_lab_history",
    "target_sem_lab_count",
    "prev_lab_sessions_sum",
    "prev_lab_resource_views_sum",
    "prev_lab_assessment_attempts_sum",
    "prev_lab_late_submission_rate",
]

THEORY_FEATURE_CONTRACT = SHARED_FEATURES + THEORY_SPECIFIC_FEATURES
PRACTICAL_FEATURE_CONTRACT = SHARED_FEATURES + PRACTICAL_SPECIFIC_FEATURES


def load_raw_tables(data_dir: str = DEFAULT_DATA_DIR) -> Dict[str, pd.DataFrame]:
    """Load the genuinely required 27-table export CSVs."""
    print(f"Loading raw tables from: {data_dir}")
    subjects = pd.read_csv(os.path.join(data_dir, "subjects.csv"))
    ssp = pd.read_csv(os.path.join(data_dir, "student_subject_performance.csv"), low_memory=False)
    sss = pd.read_csv(os.path.join(data_dir, "student_semester_summary.csv"))
    students = pd.read_csv(os.path.join(data_dir, "students.csv"))
    sla = pd.read_csv(
        os.path.join(data_dir, "student_learning_activity.csv"),
        usecols=[
            "student_id",
            "subject_id",
            "semester_no",
            "learning_sessions",
            "resource_views",
            "assessment_attempts",
            "late_submission_rate",
        ],
    )
    return {
        "subjects": subjects,
        "ssp": ssp,
        "sss": sss,
        "students": students,
        "sla": sla,
    }


def build_m2_tp_datasets(data_dir: str = DEFAULT_DATA_DIR) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build M2_T and M2_P feature-target datasets with zero temporal leakage.
    
    Returns:
        df_theory: DataFrame containing student_id, semester_no, target_theory_pct, and THEORY_FEATURE_CONTRACT.
        df_practical: DataFrame containing student_id, semester_no, target_lab_pct, and PRACTICAL_FEATURE_CONTRACT.
    """
    tables = load_raw_tables(data_dir)
    subjects = tables["subjects"]
    ssp = tables["ssp"]
    sss = tables["sss"]
    students = tables["students"]
    sla = tables["sla"]

    # Merge subjects with performance
    subj_meta = subjects[["subject_id", "subject_type", "credits"]].drop_duplicates()
    ssp_merged = ssp.merge(subj_meta, on="subject_id", how="left")

    # Only finalized subject records (percentage and end_sem_marks non-null)
    ssp_completed = ssp_merged[
        ssp_merged["percentage"].notna() & ssp_merged["end_sem_marks"].notna()
    ].copy()

    # Merge subjects with SLA
    sla_merged = sla.merge(subj_meta, on="subject_id", how="left")

    # Pre-index tables by student_id for high-speed deterministic processing
    students_dict = students.set_index("student_id").to_dict(orient="index")
    sss_by_student = sss.groupby("student_id")
    ssp_by_student = ssp_completed.groupby("student_id")
    sla_by_student = sla_merged.groupby("student_id")
    all_ssp_by_student = ssp_merged.groupby("student_id")

    theory_rows = []
    practical_rows = []

    all_student_ids = sorted(students["student_id"].unique())
    print(f"Building M2-TP datasets for {len(all_student_ids)} students...")

    for sid in all_student_ids:
        s_info = students_dict.get(sid, {})
        dept = s_info.get("department_code", 1)
        gender = str(s_info.get("gender", "Other"))
        category = str(s_info.get("category", "General"))
        adm_year = int(s_info.get("admission_year", 2021))

        # Student summaries
        if sid not in sss_by_student.groups:
            continue
        stu_sss = sss_by_student.get_group(sid)

        # Student completed subject performance
        stu_ssp = ssp_by_student.get_group(sid) if sid in ssp_by_student.groups else pd.DataFrame()
        stu_all_ssp = all_ssp_by_student.get_group(sid) if sid in all_ssp_by_student.groups else pd.DataFrame()
        stu_sla = sla_by_student.get_group(sid) if sid in sla_by_student.groups else pd.DataFrame()

        # For target semester S from 2 to 7
        for S in range(2, 8):
            # Check if student has history strictly before S
            prior_sss = stu_sss[(stu_sss["semester_no"] < S) & (stu_sss["semester_percentage"] > 0)]
            if len(prior_sss) == 0:
                # No prior completed semester -> cannot predict next semester
                continue

            prior_ssp = stu_ssp[stu_ssp["semester_no"] < S]
            prior_sla = stu_sla[stu_sla["semester_no"] < S] if len(stu_sla) > 0 else pd.DataFrame()

            # Target semester registration / metadata (available at course registration before semester starts)
            target_all_ssp = stu_all_ssp[stu_all_ssp["semester_no"] == S]
            target_tot_credits = float(target_all_ssp["credits"].sum()) if len(target_all_ssp) > 0 else 0.0

            # Completed target subjects for semester S
            target_ssp = stu_ssp[stu_ssp["semester_no"] == S]
            target_theory = target_ssp[target_ssp["subject_type"] == "Theory"]
            target_lab = target_ssp[target_ssp["subject_type"] == "Laboratory"]

            # --- Shared historical features (strict S_h < S) ---
            prev_completed = int(len(prior_sss))
            overall_sgpa_mean = float(prior_sss["semester_sgpa"].mean())
            overall_pct_mean = float(prior_sss["semester_percentage"].mean())
            overall_att_mean = float(prior_sss["semester_attendance_percentage"].mean())
            cumulative_backlogs = float(prior_sss["backlog_count"].sum())

            # Latest completed semester (immediately preceding S)
            latest_sem_row = prior_sss.sort_values("semester_no").iloc[-1]
            latest_sgpa = float(latest_sem_row["semester_sgpa"])
            latest_pct = float(latest_sem_row["semester_percentage"])
            latest_att = float(latest_sem_row["semester_attendance_percentage"])

            shared_dict = {
                "student_id": sid,
                "target_semester_no": S,
                "department_code": dept,
                "gender": gender,
                "category": category,
                "admission_year": adm_year,
                "prev_completed_semesters": prev_completed,
                "prev_overall_sgpa_mean": round(overall_sgpa_mean, 4),
                "prev_overall_pct_mean": round(overall_pct_mean, 4),
                "prev_overall_attendance_mean": round(overall_att_mean, 4),
                "prev_cumulative_backlogs": cumulative_backlogs,
                "latest_sem_sgpa": round(latest_sgpa, 4),
                "latest_sem_pct": round(latest_pct, 4),
                "latest_sem_attendance": round(latest_att, 4),
                "target_sem_total_credits": target_tot_credits,
            }

            # =========================================================================
            # M2_T: Theory Performance Dataset
            # =========================================================================
            if len(target_theory) > 0:
                target_theory_pct = float(target_theory["percentage"].mean())
                prior_theory = prior_ssp[prior_ssp["subject_type"] == "Theory"]

                if len(prior_theory) > 0:
                    t_pct_mean = float(prior_theory["percentage"].mean())
                    t_pct_std = float(prior_theory["percentage"].std()) if len(prior_theory) > 1 else 0.0
                    t_pct_min = float(prior_theory["percentage"].min())
                    t_pct_max = float(prior_theory["percentage"].max())

                    # Theory performance in latest completed semester
                    latest_prior_sem = latest_sem_row["semester_no"]
                    latest_sem_theory = prior_theory[prior_theory["semester_no"] == latest_prior_sem]
                    latest_t_pct = float(latest_sem_theory["percentage"].mean()) if len(latest_sem_theory) > 0 else t_pct_mean
                    t_trend = latest_t_pct - t_pct_mean

                    t_int_avg = float(prior_theory["internal_marks"].mean())
                    t_mid_avg = float(prior_theory["mid_sem_marks"].mean())
                    t_assign_avg = float(prior_theory["assignment_score"].dropna().mean()) if prior_theory["assignment_score"].notna().any() else np.nan
                    t_quiz_avg = float(prior_theory["quiz_avg_marks"].dropna().mean()) if prior_theory["quiz_avg_marks"].notna().any() else np.nan
                    t_delay_avg = float(prior_theory["submission_delay_days"].dropna().mean()) if prior_theory["submission_delay_days"].notna().any() else np.nan
                    t_pre_avg = float(prior_theory["pre_endsem_assessment_pct"].dropna().mean()) if prior_theory["pre_endsem_assessment_pct"].notna().any() else np.nan
                    t_count = int(len(prior_theory))
                else:
                    t_pct_mean = overall_pct_mean
                    t_pct_std = 0.0
                    t_pct_min = overall_pct_mean
                    t_pct_max = overall_pct_mean
                    latest_t_pct = overall_pct_mean
                    t_trend = 0.0
                    t_int_avg = np.nan
                    t_mid_avg = np.nan
                    t_assign_avg = np.nan
                    t_quiz_avg = np.nan
                    t_delay_avg = np.nan
                    t_pre_avg = np.nan
                    t_count = 0

                # Theory learning activity
                prior_theory_sla = prior_sla[prior_sla["subject_type"] == "Theory"] if len(prior_sla) > 0 else pd.DataFrame()
                if len(prior_theory_sla) > 0:
                    t_sessions = float(prior_theory_sla["learning_sessions"].sum())
                    t_views = float(prior_theory_sla["resource_views"].sum())
                    t_attempts = float(prior_theory_sla["assessment_attempts"].sum())
                    t_late_rate = float(prior_theory_sla["late_submission_rate"].mean())
                else:
                    t_sessions = 0.0
                    t_views = 0.0
                    t_attempts = 0.0
                    t_late_rate = 0.0

                target_t_count = int(len(target_all_ssp[target_all_ssp["subject_type"] == "Theory"]))

                row_t = {
                    **shared_dict,
                    "target_theory_pct": round(target_theory_pct, 4),
                    "prev_theory_pct_mean": round(t_pct_mean, 4),
                    "prev_theory_pct_std": round(t_pct_std, 4),
                    "prev_theory_pct_min": round(t_pct_min, 4),
                    "prev_theory_pct_max": round(t_pct_max, 4),
                    "latest_sem_theory_pct": round(latest_t_pct, 4),
                    "theory_pct_trend": round(t_trend, 4),
                    "prev_theory_internal_avg": round(t_int_avg, 4) if not np.isnan(t_int_avg) else np.nan,
                    "prev_theory_midsem_avg": round(t_mid_avg, 4) if not np.isnan(t_mid_avg) else np.nan,
                    "prev_theory_assignment_avg": round(t_assign_avg, 4) if not np.isnan(t_assign_avg) else np.nan,
                    "prev_theory_quiz_avg": round(t_quiz_avg, 4) if not np.isnan(t_quiz_avg) else np.nan,
                    "prev_theory_submission_delay_avg": round(t_delay_avg, 4) if not np.isnan(t_delay_avg) else np.nan,
                    "prev_theory_pre_endsem_pct_avg": round(t_pre_avg, 4) if not np.isnan(t_pre_avg) else np.nan,
                    "prev_theory_count": t_count,
                    "target_sem_theory_count": target_t_count,
                    "prev_theory_sessions_sum": t_sessions,
                    "prev_theory_resource_views_sum": t_views,
                    "prev_theory_assessment_attempts_sum": t_attempts,
                    "prev_theory_late_submission_rate": round(t_late_rate, 4),
                }
                theory_rows.append(row_t)

            # =========================================================================
            # M2_P: Practical / Laboratory Performance Dataset
            # =========================================================================
            if len(target_lab) > 0:
                target_lab_pct = float(target_lab["percentage"].mean())
                prior_lab = prior_ssp[prior_ssp["subject_type"] == "Laboratory"]

                if len(prior_lab) > 0:
                    l_pct_mean = float(prior_lab["percentage"].mean())
                    l_pct_std = float(prior_lab["percentage"].std()) if len(prior_lab) > 1 else 0.0
                    l_pct_min = float(prior_lab["percentage"].min())
                    l_pct_max = float(prior_lab["percentage"].max())

                    # Lab performance in most recent prior semester that had labs
                    most_recent_lab_sem = prior_lab["semester_no"].max()
                    recent_sem_lab = prior_lab[prior_lab["semester_no"] == most_recent_lab_sem]
                    latest_l_pct = float(recent_sem_lab["percentage"].mean())
                    l_trend = latest_l_pct - l_pct_mean

                    l_int_avg = float(prior_lab["internal_marks"].mean())
                    l_mid_avg = float(prior_lab["mid_sem_marks"].mean())
                    l_assign_avg = float(prior_lab["assignment_score"].dropna().mean()) if prior_lab["assignment_score"].notna().any() else np.nan
                    l_quiz_avg = float(prior_lab["quiz_avg_marks"].dropna().mean()) if prior_lab["quiz_avg_marks"].notna().any() else np.nan
                    l_delay_avg = float(prior_lab["submission_delay_days"].dropna().mean()) if prior_lab["submission_delay_days"].notna().any() else np.nan
                    l_pre_avg = float(prior_lab["pre_endsem_assessment_pct"].dropna().mean()) if prior_lab["pre_endsem_assessment_pct"].notna().any() else np.nan
                    l_count = int(len(prior_lab))
                    has_prior_lab = 1.0
                else:
                    # e.g. student who has no lab subjects in prior history
                    l_pct_mean = np.nan
                    l_pct_std = 0.0
                    l_pct_min = np.nan
                    l_pct_max = np.nan
                    latest_l_pct = np.nan
                    l_trend = 0.0
                    l_int_avg = np.nan
                    l_mid_avg = np.nan
                    l_assign_avg = np.nan
                    l_quiz_avg = np.nan
                    l_delay_avg = np.nan
                    l_pre_avg = np.nan
                    l_count = 0
                    has_prior_lab = 0.0

                # Lab learning activity
                prior_lab_sla = prior_sla[prior_sla["subject_type"] == "Laboratory"] if len(prior_sla) > 0 else pd.DataFrame()
                if len(prior_lab_sla) > 0:
                    l_sessions = float(prior_lab_sla["learning_sessions"].sum())
                    l_views = float(prior_lab_sla["resource_views"].sum())
                    l_attempts = float(prior_lab_sla["assessment_attempts"].sum())
                    l_late_rate = float(prior_lab_sla["late_submission_rate"].mean())
                else:
                    l_sessions = 0.0
                    l_views = 0.0
                    l_attempts = 0.0
                    l_late_rate = 0.0

                target_l_count = int(len(target_all_ssp[target_all_ssp["subject_type"] == "Laboratory"]))

                row_p = {
                    **shared_dict,
                    "target_lab_pct": round(target_lab_pct, 4),
                    "prev_lab_pct_mean": round(l_pct_mean, 4) if not np.isnan(l_pct_mean) else np.nan,
                    "prev_lab_pct_std": round(l_pct_std, 4),
                    "prev_lab_pct_min": round(l_pct_min, 4) if not np.isnan(l_pct_min) else np.nan,
                    "prev_lab_pct_max": round(l_pct_max, 4) if not np.isnan(l_pct_max) else np.nan,
                    "latest_sem_lab_pct": round(latest_l_pct, 4) if not np.isnan(latest_l_pct) else np.nan,
                    "lab_pct_trend": round(l_trend, 4),
                    "prev_lab_internal_avg": round(l_int_avg, 4) if not np.isnan(l_int_avg) else np.nan,
                    "prev_lab_midsem_avg": round(l_mid_avg, 4) if not np.isnan(l_mid_avg) else np.nan,
                    "prev_lab_assignment_avg": round(l_assign_avg, 4) if not np.isnan(l_assign_avg) else np.nan,
                    "prev_lab_quiz_avg": round(l_quiz_avg, 4) if not np.isnan(l_quiz_avg) else np.nan,
                    "prev_lab_submission_delay_avg": round(l_delay_avg, 4) if not np.isnan(l_delay_avg) else np.nan,
                    "prev_lab_pre_endsem_pct_avg": round(l_pre_avg, 4) if not np.isnan(l_pre_avg) else np.nan,
                    "prev_lab_count": l_count,
                    "has_prior_lab_history": has_prior_lab,
                    "target_sem_lab_count": target_l_count,
                    "prev_lab_sessions_sum": l_sessions,
                    "prev_lab_resource_views_sum": l_views,
                    "prev_lab_assessment_attempts_sum": l_attempts,
                    "prev_lab_late_submission_rate": round(l_late_rate, 4),
                }
                practical_rows.append(row_p)

    df_theory = pd.DataFrame(theory_rows)
    df_practical = pd.DataFrame(practical_rows)

    print(f"M2_T dataset constructed: {len(df_theory)} samples across {df_theory['student_id'].nunique()} students.")
    print(f"M2_P dataset constructed: {len(df_practical)} samples across {df_practical['student_id'].nunique()} students.")

    return df_theory, df_practical


if __name__ == "__main__":
    df_t, df_p = build_m2_tp_datasets()
    print("\n--- M2_T Target Summary ---")
    print(df_t["target_theory_pct"].describe())
    print("\nM2_T Semester Distribution:")
    print(df_t["target_semester_no"].value_counts().sort_index())

    print("\n--- M2_P Target Summary ---")
    print(df_p["target_lab_pct"].describe())
    print("\nM2_P Semester Distribution:")
    print(df_p["target_semester_no"].value_counts().sort_index())
