# -*- coding: utf-8 -*-
"""
Deterministic, realism-focussed cleanup of the Supabase export (27 tables).

Rules derived from the dataset's OWN internally-consistent 6A cohort:
  - grade bands: >=90 O, 80-89.999 A+, 70-79.999 A, 60-69.999 B+, 50-59.999 B,
                 40-49.999 C, <40 F ; grade_point 10/9/8/7/6/5/0
  - performance_category: Top >=90, Above Average 80-89.999, Average 60-79.999,
                          Below Average 40-59.999, Low Performer <40
  - pre_endsem_assessment_pct = (internal+mid)/70*100
  - summary analytics: sgpa_drift=sgpa-prev_sgpa ; sgpa_rolling_mean_3=mean(last3 sgpa)
                       backlog_change=backlog-prev_backlog ;
                       cumulative_backlog_events=cumsum(backlog)
                       backlog_trajectory=cumulative/semester_no
  - students.csv derives from summaries: overall_cgpa=credit-wt sgpa,
       latest_sgpa=last sem sgpa, overall_percentage=credit-wt pct

Realism constraints applied:
  - total backlogs capped at 8 (worst realistic), max 4 per later sem, max 2 in sem 1
  - legacy current semester (CSE sem-7, BBA sem-5) end-sem results generated
    from internal+mid trajectory with seeded best/worst case variance
  - plaintext passwords replaced with deterministic pbkdf2-style hashes
  - ml prediction_value serialized as proper JSON
  - epoch timestamps normalized, model_versions unified
"""
import os
import ast
import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

pd.options.future.infer_string = False  # avoid flaky _Printer-proxy str storage (pandas 3.0)

SRC = r"D:\KenexAi\ByteBrain\supabase_export_04_09_latest_27table"
DST = r"D:\KenexAi\ByteBrain\supabase_export_fixed"
os.makedirs(DST, exist_ok=True)

rng = np.random.default_rng(20260831)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def load(name):
    df = pd.read_csv(os.path.join(SRC, name), dtype=str, low_memory=False)
    return df.astype(object)


def save(df, name):
    df.to_csv(os.path.join(DST, name), index=False)


def pct_band(pct):
    if pct >= 90:
        return ("O", 10.0, "Top")
    if pct >= 80:
        return ("A+", 9.0, "Above Average")
    if pct >= 70:
        return ("A", 8.0, "Average")
    if pct >= 60:
        return ("B+", 7.0, "Average")
    if pct >= 50:
        return ("B", 6.0, "Below Average")
    if pct >= 40:
        return ("C", 5.0, "Below Average")
    return ("F", 0.0, "Low Performer")


def hash_password(pw, salt):
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()
    return "pbkdf2_sha256$100000$%s$%s" % (salt, h)


print("== loading ==")
students = load("students.csv")
summary = load("student_semester_summary.csv")
perf = load("student_subject_performance.csv")
enroll = load("student_subject_enrollment.csv")
attendance = load("attendance.csv")
faculty = load("faculty.csv")
subjects = load("subjects.csv")
fsm = load("faculty_student_map.csv")
users = load("users.csv")
goals = load("student_goals.csv")
messages = load("student_messages.csv")
timetable = load("weekly_timetable_07.csv")
ml_predictions = load("ml_predictions.csv")
risk_predictions = load("risk_predictions.csv")
prediction_feedback = load("prediction_feedback.csv")

legacy_ids = students.loc[~students["student_id"].str.contains("6A"), "student_id"].tolist()
sixa_ids = students.loc[students["student_id"].str.contains("6A"), "student_id"].tolist()

# ---------------------------------------------------------------------------
# 1. ml_predictions : JSON payload + unified model_version
# ---------------------------------------------------------------------------
ml_predictions["prediction_value"] = ml_predictions["prediction_value"].apply(
    lambda v: json.dumps(ast.literal_eval(v), separators=(", ", ": "), ensure_ascii=False)
)
ml_predictions["model_version"] = ml_predictions["model_version"].fillna("1").astype(str).str.replace("1.0", "1", regex=False)
print("ml_predictions: payloads JSON, model_version values ->", sorted(ml_predictions["model_version"].unique()))

# ---------------------------------------------------------------------------
# 2. risk_predictions : epoch -> ISO naive datetime, aligned created/updated
# ---------------------------------------------------------------------------
def epoch_to_dt(ts):
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


risk_predictions["prediction_timestamp"] = risk_predictions["prediction_timestamp"].apply(
    lambda ts: epoch_to_dt(ts).strftime("%Y-%m-%d %H:%M:%S.%f")
)
risk_predictions["created_at"] = risk_predictions["prediction_timestamp"].apply(
    lambda s: s[:10]
)
risk_predictions["updated_at"] = risk_predictions.apply(
    lambda r: (datetime.strptime(r["prediction_timestamp"], "%Y-%m-%d %H:%M:%S.%f")
               + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S.%f"),
    axis=1,
)
print("risk_predictions: timestamps normalized (sample)", risk_predictions["prediction_timestamp"].iloc[0])

# ---------------------------------------------------------------------------
# 3. prediction_feedback : model_version
# ---------------------------------------------------------------------------
prediction_feedback["model_version"] = prediction_feedback["model_version"].fillna("1")
print("prediction_feedback: model_version filled", prediction_feedback["model_version"].isna().sum(), "nulls left")

# ---------------------------------------------------------------------------
# 4. users : hash passwords + add 6A student accounts
# ---------------------------------------------------------------------------
uids = users["user_id"].str.extract(r"(\d+)$")[0].astype(int)
next_uid = int(uids.max()) + 1

users["password"] = [
    hash_password(pw, "k%d" % i)
    for i, pw in enumerate(users["password"])
]

six_users = students[students["student_id"].str.contains("6A")].copy()
new_users = pd.DataFrame({
    "user_id": ["USR%06d" % (next_uid + k) for k in range(len(six_users))],
    "username": six_users["enrollment_no"].values,
    "email": six_users["email"].values,
    "password": [hash_password("kenexai@" + str(k + 1), "6A%d" % k) for k in range(len(six_users))],
    "role": ["Student"] * len(six_users),
    "student_id": six_users["student_id"].values,
    "faculty_id": [""] * len(six_users),
    "department": ["CSE"] * len(six_users),
    "is_active": ["True"] * len(six_users),
    "created_at": six_users["created_at"].values,
    "preferences": [""] * len(six_users),
})
users = pd.concat([users, new_users], ignore_index=True)
print("users: passwords hashed, added", len(new_users), "6A student accounts (total", len(users), ")")

# ---------------------------------------------------------------------------
# 5. subject -> subject_domain / subject_skill map (from consistent 6A rows)
# ---------------------------------------------------------------------------
en6 = enroll[enroll["student_id"].str.contains("6A")]
subj_map = en6.groupby("subject_id").agg(
    subject_domain=("subject_domain", lambda s: s.value_counts().index[0]),
    subject_skill=("subject_skill", lambda s: s.value_counts().index[0]),
).reset_index()

legacy_div = students.set_index("student_id")["current_semester"].to_dict()

# ---------------------------------------------------------------------------
# 6. performance : backfill legacy fields + generate current-sem end results
# ---------------------------------------------------------------------------
perf["_is6"] = perf["student_id"].str.contains("6A")
perf.loc[~perf["_is6"], "division"] = perf.loc[~perf["_is6"], "student_id"].map(
    lambda sid: "%sA" % legacy_div[sid]
)
# numeric cols
for c in ["internal_marks", "mid_sem_marks", "end_sem_marks"]:
    perf[c] = pd.to_numeric(perf[c], errors="coerce")

# join domain/skill
perf = perf.merge(subj_map, on="subject_id", how="left")
perf.loc[~perf["_is6"], "subject_domain"] = perf.loc[~perf["_is6"], "subject_domain_x"]
perf.loc[~perf["_is6"], "subject_skill"] = perf.loc[~perf["_is6"], "subject_skill_x"]
perf = perf.drop(columns=["subject_domain_x", "subject_skill_x"])

# pre_endsem etc for legacy rows
leg_mask = ~perf["_is6"]
i_marks = perf["internal_marks"].fillna(0)
m_marks = perf["mid_sem_marks"].fillna(0)
pre_pct = (i_marks + m_marks) / 70.0 * 100.0
perf.loc[leg_mask, "pre_endsem_assessment_pct"] = pre_pct.round(2)
perf.loc[leg_mask, "assignment_score"] = np.clip(pre_pct + rng.normal(0, 6, len(perf)), 0, 100).round(2)
perf.loc[leg_mask, "quiz_avg_marks"] = np.clip(pre_pct + rng.normal(0, 7, len(perf)), 0, 100).round(2)
perf.loc[leg_mask, "submission_delay_days"] = pd.Series(
    np.clip(rng.gamma(1.2, 1.0, len(perf)), 0, 8.5).round(2), index=perf.index
)

# --- generate realistic end-sem results for legacy current semester (end_sem null)
cur_row = perf[leg_mask & perf["end_sem_marks"].isna()].index
print("performance rows missing end_sem (legacy current sem) ->", len(cur_row))
end_noise = rng.normal(0, 5, len(cur_row))
end_improve = np.clip((52.0 - pre_pct.loc[cur_row].values) * 0.045, 0.0, 5.0)
perp_vals = np.clip(pre_pct.loc[cur_row].values * 0.70 + end_improve + end_noise, 0.0, 70.0).round(1)
perf.loc[cur_row, "end_sem_marks"] = pd.Series(perp_vals, index=cur_row)

# recompute derived performance fields for all legacy rows
tot = perf["internal_marks"] + perf["mid_sem_marks"] + perf["end_sem_marks"]
pc = (tot / 140.0 * 100.0).round(2)
perf.loc[leg_mask, "total_marks"] = tot.round(1)
perf.loc[leg_mask, "percentage"] = pc
band = pc.apply(pct_band)
perf.loc[leg_mask, "grade"] = pd.Series([b[0] for b in band], index=perf.index)
perf.loc[leg_mask, "grade_point"] = pd.Series([b[1] for b in band], index=perf.index)
perf.loc[leg_mask, "performance_category"] = pd.Series([b[2] for b in band], index=perf.index)
_gs = perf.loc[leg_mask, "grade"]
perf.loc[leg_mask, "result_status"] = pd.Series(
    np.where(_gs == "F", "Fail", "Pass"), index=_gs.index
)
remarks = {"O": "Excellent", "A+": "Good", "A": "Good", "B+": "Average",
           "B": "Average", "C": "Below Average", "F": "Needs Improvement"}
perf.loc[leg_mask, "remarks"] = perf.loc[leg_mask, "grade"].map(remarks)

# audit trail on the rows we touched this cycle + current-sem rows
perf.loc[cur_row, "updated_at"] = "2026-08-31 05:40:46.457466"
perf.loc[cur_row, "updated_by"] = "USR000106"
perf = perf.drop(columns=["_is6"])

# ---------------------------------------------------------------------------
# 7. Backlog realism cap for extreme legacy students
# ---------------------------------------------------------------------------
perf["gp"] = pd.to_numeric(perf["grade_point"], errors="coerce")
perf["failed"] = perf["gp"].eq(0)
perf["sem_n"] = pd.to_numeric(perf["semester_no"])

def sem_fails(pid):
    perf["gp"] = pd.to_numeric(perf["grade_point"], errors="coerce")
    perf["failed"] = perf["gp"].eq(0)
    return perf[perf["student_id"] == pid].groupby("semester_no")["failed"].sum().to_dict()


CAP_TOTAL, CAP_LATE, CAP_SEM1 = 8, 4, 2
extreme = ["STU000032", "STU000041", "STU000052", "STU000060", "STU000064", "STU000075"]
flipped = []


def refresh_fails(pid):
    perf["gp"] = pd.to_numeric(perf["grade_point"], errors="coerce")
    perf["failed"] = perf["gp"].eq(0)
    return perf[perf["student_id"] == pid].groupby("semester_no")["failed"].sum().to_dict()


for pid in extreme:
    cur_sem = int(legacy_div[pid])
    fails = refresh_fails(pid)
    guard = 0
    while sum(fails.values()) > CAP_TOTAL and guard < 300:
        guard += 1
        target = None
        if fails.get("1", 0) > CAP_SEM1:
            target = "1"
        else:
            bad_late = [s for s in fails if float(s) > 1 and fails[s] > CAP_LATE]
            if bad_late:
                target = bad_late[0]
            else:
                cand = [s for s in fails if float(s) < cur_sem and fails[s] > 0]
                if not cand:
                    break
                target = cand[-1]
        cand_rows = perf[(perf["student_id"] == pid)
                         & (perf["semester_no"] == target)
                         & perf["failed"]].sort_values(
            ["internal_marks", "mid_sem_marks"], ascending=False)
        if cand_rows.empty:
            break
        idx = cand_rows.index[0]
        i = float(perf.loc[idx, "internal_marks"])
        m = float(perf.loc[idx, "mid_sem_marks"])
        new_end = max(0.0, round(62.0 - (i + m), 1))
        nt = i + m + new_end
        npct = round(nt / 140.0 * 100.0, 2)
        if npct < 40.0 or npct > 49.99:
            new_end = max(0.0, round(60.0 - (i + m), 1))
            nt = i + m + new_end
            npct = round(nt / 140.0 * 100.0, 2)
        perf.loc[idx, "end_sem_marks"] = new_end
        perf.loc[idx, "total_marks"] = round(nt, 1)
        perf.loc[idx, "percentage"] = npct
        perf.loc[idx, "grade"] = "C"
        perf.loc[idx, "grade_point"] = 5.0
        perf.loc[idx, "performance_category"] = "Below Average"
        perf.loc[idx, "result_status"] = "Pass"
        perf.loc[idx, "remarks"] = "Cleared (repeat attempt)"
        perf.loc[idx, "updated_at"] = "2026-08-31 05:40:46.457466"
        perf.loc[idx, "updated_by"] = "USR000106"
        flipped.append(idx)
        fails = refresh_fails(pid)

print("flipped fails to cleared passes:", len(flipped))
for pid in extreme:
    fr = refresh_fails(pid)
    print("  %s final per-sem fails = %s  total=%d" % (pid, fr, sum(fr.values())))

# re-evaluate per-sem caps (few remain from current sem -> realistic worst case)
for pid in extreme:
    fr = refresh_fails(pid)
    print("  check caps", pid, "sem1", fr.get("1", 0), "late max",
          max([v for s, v in fr.items() if float(s) > 1] or [0]))

# ---------------------------------------------------------------------------
# 8. Rebuild semester summaries for the legacy cohort + repair 6A mismatches
# ---------------------------------------------------------------------------
# mark which legacy semesters are the CURRENT (regenerate fully) vs completed
cur_sem_map = {sid: int(sem) for sid, sem in legacy_div.items()}

# per (student,sem) aggregates from performance
# credits per subject
credit_map = enroll.groupby("enrollment_record_id")["credits"].first().to_dict()
p_weight = perf[~perf["student_id"].str.contains("6A")].copy()
p_weight["credit_p"] = [credit_map.get(x) for x in p_weight["enrollment_record_id"]]
p_weight["credit_p"] = pd.to_numeric(p_weight["credit_p"], errors="coerce")
p_weight["w"] = pd.to_numeric(p_weight["gp"], errors="coerce") * p_weight["credit_p"]
perf_agg = perf[~perf["student_id"].str.contains("6A")].groupby(["student_id", "semester_no"]).agg(
    n_subj=("subject_id", "count"),
    total_subj=("total_marks", lambda s: pd.to_numeric(s, errors="coerce").sum()),
    n_fail=("failed", "sum"),
).reset_index()
pweight_agg = p_weight.groupby(["student_id", "semester_no"]).agg(
    sgpa_wt=("w", "sum"), crsum=("credit_p", "sum")
).reset_index()
perf_agg = perf_agg.merge(pweight_agg, on=["student_id", "semester_no"], how="left")
perf_agg["sgpa_wt"] = perf_agg["sgpa_wt"] / perf_agg["crsum"]

# credits per subject
credit_map = enroll.groupby("enrollment_record_id")["credits"].first().to_dict()

def rebuild_legacy_summaries():
    global summary
    ss = summary.copy()
    ss["sem"] = pd.to_numeric(ss["semester_no"])
    enrolled_credits = enroll[["student_id", "semester_no", "enrollment_record_id"]]
    ec = enrolled_credits.copy()
    ec["credit"] = pd.to_numeric([credit_map.get(x) for x in ec["enrollment_record_id"]], errors="coerce")
    cred_agg = ec[~ec["student_id"].str.contains("6A")].groupby(["student_id", "semester_no"])[
        "credit"].sum().rename("credits_sum")

    for _, r in perf_agg.iterrows():
        pid, sem = r["student_id"], r["semester_no"]
        cur = (int(float(sem)) == cur_sem_map[pid])
        mask = (ss["student_id"] == pid) & (ss["semester_no"] == sem)
        n = int(r["n_subj"])
        tot = float(r["total_subj"])
        pct = round(tot / (140.0 * n) * 100.0, 2)
        gp_w = float(r["sgpa_wt"] or 0) if not pd.isna(r["sgpa_wt"]) else float("nan")
        cr = float(cred_agg.loc[(pid, sem)]) if (pid, sem) in cred_agg.index else float("nan")
        back = int(r["n_fail"])
        grade = pct_band(pct)[0] if not pd.isna(pct) else "B"
        att = att_agg.get((pid, sem), None)
        ss.loc[mask, "division"] = "%sA" % legacy_div[pid]
        ss.loc[mask, "semester_total_marks"] = round(tot, 1)
        ss.loc[mask, "semester_percentage"] = pct
        ss.loc[mask, "semester_sgpa"] = round(gp_w, 2)
        ss.loc[mask, "semester_grade"] = grade
        ss.loc[mask, "semester_result"] = "ATKT" if back > 0 else "PASS"
        ss.loc[mask, "backlog_count"] = back
        ss.loc[mask, "credits_registered"] = cr
        ss.loc[mask, "credits_earned"] = max(cr - back * 3.0, 0.0)
        if att is not None:
            ss.loc[mask, "semester_attendance_percentage"] = round(att, 2)
        # realistic standing from result + pct
        if back > 0:
            standing = "Average" if back <= 2 else "Needs Improvement"
        else:
            standing = "Good" if pct >= 70 else "Average"
        ss.loc[mask, "academic_standing"] = standing
        ss.loc[mask, "is_m1_deployment_boundary"] = "True"
        ss.loc[mask, "target_available_if_completed"] = "True"
    return ss


# attendance aggregates for legacy per (student,sem): mean subject attendance
attendance["_att_pct"] = 100.0 * pd.to_numeric(attendance["attended_classes"]) / pd.to_numeric(attendance["total_classes"])
att_agg = dict(attendance[~attendance["student_id"].str.contains("6A")]
               .groupby(["student_id", "semester_no"])["_att_pct"].mean())


def fill_analytics(df):
    """fill derived analytics columns following the 6A formulas (in place)."""
    out = df.copy()
    out["sem"] = pd.to_numeric(out["semester_no"])
    out["sg"] = pd.to_numeric(out["semester_sgpa"], errors="coerce")
    out["bc"] = pd.to_numeric(out["backlog_count"], errors="coerce").fillna(0)
    out = out.sort_values(["student_id", "sem"]).reset_index(drop=True)
    g = out.groupby("student_id")
    out["previous_sem_sgpa"] = g["sg"].shift(1)
    out["sgpa_drift"] = (out["sg"] - out["previous_sem_sgpa"]).round(2)
    out["sgpa_rolling_mean_3"] = g["sg"].transform(lambda s: s.rolling(3, min_periods=1).mean()).round(3)
    out["previous_sem_backlog_count"] = g["bc"].shift(1).fillna(0)
    out["backlog_change"] = (out["bc"] - out["previous_sem_backlog_count"]).round(1)
    out["cumulative_backlog_events"] = g["bc"].cumsum()
    out["backlog_trajectory"] = (out["cumulative_backlog_events"] / out["sem"]).round(4)
    out["attendance_aggregate_pct"] = out["_att_proxy"]
    # attendance proxied from semester_attendance_percentage
    out["attendance_aggregate_pct"] = pd.to_numeric(out["semester_attendance_percentage"], errors="coerce")
    return out.drop(columns=["sem", "sg", "bc"])


summary = summary.assign(_att_proxy=pd.to_numeric(summary["semester_attendance_percentage"], errors="coerce"))
summary = rebuild_legacy_summaries()
summary = fill_analytics(summary)

# repair the 7 (sixA) summary rows that claimed a backlog without a failing subject
sixa_mismatch = []
for pid, sem in [("STU6A0002", "2"), ("STU6A0404", "4"), ("STU6A0488", "1"),
                 ("STU6A0598", "6"), ("STU6A0761", "4"), ("STU6A0878", "7"), ("STU6A1130", "1")]:
    nfail = perf[(perf["student_id"] == pid) & (perf["semester_no"] == sem)]["failed"].sum()
    if nfail == 0:
        mask = (summary["student_id"] == pid) & (summary["semester_no"] == sem)
        summary.loc[mask, "backlog_count"] = 0
        summary.loc[mask, "semester_result"] = "PASS"
        sixa_mismatch.append((pid, sem))
print("6A summary rows repaired (claimed backlog, no failing grade):", sixa_mismatch)
summary = summary.fillna({"backlog_change": 0, "previous_sem_backlog_count": 0,
                          "cumulative_backlog_events": summary["backlog_count"].astype(float).cumsum()
                          if "backlog_count" in summary else 0})

# re-derive those repaired rows' analytics quickly
g = summary.groupby("student_id")
summary["backlog_count_n"] = pd.to_numeric(summary["backlog_count"], errors="coerce").fillna(0)
summary["cumulative_backlog_events"] = g["backlog_count_n"].cumsum()
summary["backlog_trajectory"] = (summary["cumulative_backlog_events"]
                                 / pd.to_numeric(summary["semester_no"])).round(4)
summary["previous_sem_backlog_count"] = g["backlog_count_n"].shift(1).fillna(0)
summary["backlog_change"] = (summary["backlog_count_n"] - summary["previous_sem_backlog_count"]).round(1)
summary = summary.drop(columns=["backlog_count_n", "_att_proxy"])

# reconcile legacy division everywhere for consistency
leg_sum = summary["student_id"].isin(legacy_div)
summary.loc[leg_sum, "division"] = ["%sA" % legacy_div[sid] for sid in summary.loc[leg_sum, "student_id"]]

# ---------------------------------------------------------------------------
# 9. enrollment backfill (legacy division / domain / skill)
# ---------------------------------------------------------------------------
enroll["division"] = ["%sA" % legacy_div[sid] if sid in legacy_div else "6A" for sid in enroll["student_id"]]
enroll = enroll.merge(subj_map, on="subject_id", how="left")
enroll["subject_domain"] = enroll["subject_domain_x"].where(enroll["subject_domain_x"].notna(), enroll["subject_domain_y"])
enroll["subject_skill"] = enroll["subject_skill_x"].where(enroll["subject_skill_x"].notna(), enroll["subject_skill_y"])
enroll = enroll.drop(columns=["subject_domain_x", "subject_domain_y", "subject_skill_x", "subject_skill_y"])
enroll.loc[~enroll["student_id"].str.contains("6A"), "division"] = [
    "%sA" % legacy_div[sid] for sid in enroll.loc[~enroll["student_id"].str.contains("6A"), "student_id"]]
# BBA subjects have no 6A coverage -> assign curated domain/skill
bba_dom = {
    "SUB0058": "Management & Leadership", "SUB0059": "Communication & General",
    "SUB0060": "Finance & Accounting", "SUB0061": "Economics & Trade",
    "SUB0062": "Math & Statistics", "SUB0063": "Information Systems",
    "SUB0064": "Sustainability & Environment", "SUB0065": "Management & Leadership",
    "SUB0066": "Marketing & Communication", "SUB0067": "Math & Statistics",
    "SUB0068": "Finance & Accounting", "SUB0069": "Law & Governance",
    "SUB0070": "HR & People", "SUB0071": "Communication & General",
    "SUB0072": "Finance & Accounting", "SUB0073": "Operations & Analytics",
    "SUB0074": "Strategy & Entrepreneurship", "SUB0075": "Law & Governance",
    "SUB0076": "Information Systems", "SUB0077": "Research & Analytics",
    "SUB0078": "Communication & General", "SUB0079": "Marketing & Communication",
    "SUB0080": "Operations & Analytics", "SUB0081": "Finance & Accounting",
    "SUB0082": "Law & Governance", "SUB0083": "Digital Business",
    "SUB0084": "Operations & Analytics", "SUB0085": "Project & Internship",
    "SUB0086": "Strategy & Leadership", "SUB0087": "Economics & Trade",
    "SUB0088": "Operations & Logistics", "SUB0089": "Operations & Analytics",
    "SUB0090": "Digital Business", "SUB0091": "Operations & Analytics",
    "SUB0092": "Project & Capstone",
}
bba_skill = {
    "SUB0058": "Management", "SUB0059": "Communication", "SUB0060": "Financial Accounting",
    "SUB0061": "Economics", "SUB0062": "Mathematics", "SUB0063": "Information Systems",
    "SUB0064": "Environment & Sustainability", "SUB0065": "Organizational Behavior",
    "SUB0066": "Marketing", "SUB0067": "Statistics", "SUB0068": "Costing & Finance",
    "SUB0069": "Legal Compliance", "SUB0070": "Human Resources", "SUB0071": "Communication",
    "SUB0072": "Finance", "SUB0073": "Operations", "SUB0074": "Entrepreneurship",
    "SUB0075": "Legal Compliance", "SUB0076": "Information Systems", "SUB0077": "Research Methods",
    "SUB0078": "Soft Skills", "SUB0079": "Consumer Insights", "SUB0080": "Operations",
    "SUB0081": "Taxation", "SUB0082": "Ethics & Governance", "SUB0083": "Digital Commerce",
    "SUB0084": "Analytics", "SUB0085": "Industry Internship", "SUB0086": "Strategy",
    "SUB0087": "Global Business", "SUB0088": "Supply Chain", "SUB0089": "Project Management",
    "SUB0090": "Digital Marketing", "SUB0091": "Analytics", "SUB0092": "Capstone Project",
}
bba_side = enroll["subject_id"].isin(bba_dom)
enroll.loc[bba_side, "subject_domain"] = [bba_dom[s] for s in enroll.loc[bba_side, "subject_id"]]
enroll.loc[bba_side, "subject_skill"] = [bba_skill[s] for s in enroll.loc[bba_side, "subject_id"]]

# ---------------------------------------------------------------------------
# 10. students.csv : recompute legacy aggregates from (fixed) summaries
# ---------------------------------------------------------------------------
ss_num = summary.copy()
ss_num["sg"] = pd.to_numeric(ss_num["semester_sgpa"], errors="coerce")
ss_num["cr"] = pd.to_numeric(ss_num["credits_registered"], errors="coerce").fillna(0)
ss_num["sp"] = pd.to_numeric(ss_num["semester_percentage"], errors="coerce")
ss_num["sem"] = pd.to_numeric(ss_num["semester_no"])

last_sem = ss_num.loc[ss_num.groupby("student_id")["sem"].idxmax()][["student_id", "sg"]]
agg_cgpa = ss_num.groupby("student_id").apply(
    lambda g: (g["sg"] * g["cr"]).sum() / g["cr"].sum(), include_groups=False).rename("oc").reset_index()
agg_pct = ss_num.groupby("student_id").apply(
    lambda g: (g["sp"] * g["cr"]).sum() / g["cr"].sum(), include_groups=False).rename("op").reset_index()
agg_back = ss_num.groupby("student_id")["backlog_count"].apply(
    lambda s: pd.to_numeric(s, errors="coerce").fillna(0).astype(int).sum()).rename("nb").reset_index()

att_student = attendance.groupby("student_id").apply(
    lambda g: 100.0 * pd.to_numeric(g["attended_classes"]).sum() / pd.to_numeric(g["total_classes"]).sum(),
    include_groups=False).rename("oa").reset_index()

students = students.merge(last_sem.rename(columns={"sg": "latest_sgpa_calc"}), on="student_id", how="left")
students = students.merge(agg_cgpa, on="student_id", how="left")
students = students.merge(agg_pct, on="student_id", how="left")
students = students.merge(agg_back, on="student_id", how="left")
students = students.merge(att_student, on="student_id", how="left")

def standing(cg):
    cg = float(cg)
    if cg >= 8.0:
        return "Good"
    if cg >= 7.0:
        return "Average"
    return "Needs Improvement"

for sid in legacy_ids:
    mask = students["student_id"] == sid
    students.loc[mask, "latest_sgpa"] = students.loc[mask, "latest_sgpa_calc"].round(2)
    students.loc[mask, "overall_cgpa"] = students.loc[mask, "oc"].round(2)
    students.loc[mask, "overall_percentage"] = students.loc[mask, "op"].round(2)
    students.loc[mask, "overall_attendance_percentage"] = students.loc[mask, "oa"].round(2)
    students.loc[mask, "total_backlogs"] = students.loc[mask, "nb"]
    students.loc[mask, "academic_standing"] = students.loc[mask, "oc"].apply(standing)
    students.loc[mask, "division"] = "%sA" % legacy_div[sid]
    students.loc[mask, "cohort_id"] = "%sA_%d" % (legacy_div[sid], len(legacy_ids) and (50 if sid.startswith("STU0000") and legacy_div[sid] == "7A" else 30))
    students.loc[mask, "source_dataset"] = "migrated_gls_realistic_v1"
    students.loc[mask, "generation_version"] = ""
    students.loc[mask, "dataset_version"] = "KenexAI_legacy_migrated_v1"

students = students.drop(columns=["latest_sgpa_calc", "oc", "op", "nb", "oa"])

# ---------------------------------------------------------------------------
# 11. faculty_student_map : complete hybrid rows
# ---------------------------------------------------------------------------
reason_pool = ["Academic Mentoring Program", "Career Planning",
               "Skill Development", "Regular Allocation", "Peer Performance Review"]
fsm = fsm.sort_values("faculty_student_map_id").reset_index(drop=True)
fsm["_six"] = fsm["student_id"].str.contains("6A")
six_mask = fsm["_six"]
leg_mask = ~fsm["_six"]
fsm.loc[six_mask, "allocation_reason"] = [
    reason_pool[i % len(reason_pool)] for i in range(int(six_mask.sum()))
]
fsm.loc[leg_mask, "mapping_id"] = fsm.loc[leg_mask, "faculty_student_map_id"]
fsm.loc[leg_mask, "semester_no"] = [float(legacy_div[sid]) for sid in fsm.loc[leg_mask, "student_id"]]
fsm.loc[leg_mask, "mapping_type"] = [
    {"Faculty Advisor": "ADVISOR", "Placement Mentor": "PLACEMENT", "Academic Mentor": "MENTOR"}.get(r)
    for r in fsm.loc[leg_mask, "mentor_role"]]
fsm.loc[leg_mask, "is_active"] = "True"
fsm = fsm.drop(columns=["_six"])
print("faculty_student_map: allocation_reason filled for 6A, mapping fields for legacy")

# ---------------------------------------------------------------------------
# 12. student_goals : realistic target for every student
# ---------------------------------------------------------------------------
new_goals = []
for _, r in students.iterrows():
    sid = r["student_id"]
    cg = float(r["overall_cgpa"]) if pd.notna(r["overall_cgpa"]) else 6.0
    op = float(r["overall_percentage"]) if pd.notna(r["overall_percentage"]) else 60.0
    rnd = rng.uniform(0, 1)
    improvement = round(rng.uniform(0.15, 0.95), 2)
    if rnd < 0.55:
        gtype, gval = "target_sgpa", round(min(10.0, cg + improvement), 2)
    else:
        gtype, gval = "target_percentage", round(min(99.0, op + rng.uniform(3, 8)), 2)
    ts = datetime(2026, 8, rng.integers(25, 31), rng.integers(8, 12), rng.integers(0, 59),
                  rng.integers(0, 59)).strftime("%Y-%m-%d %H:%M:%S.%f+00:00")
    new_goals.append({
        "goal_id": str(uuid.uuid4()),
        "student_id": sid,
        "goal_type": gtype,
        "target_value": gval,
        "status": "Active",
        "created_at": ts,
        "updated_at": ts,
    })
goals = pd.DataFrame(new_goals)
print("student_goals: generated", len(goals), "rows (all students)")

# ---------------------------------------------------------------------------
# 13. student_messages : realistic attendance alerts grounded in real records
# ---------------------------------------------------------------------------
msg_rows = []
subj_fac = {}
tt_map = timetable.groupby("subject_id")["faculty_id"].agg(
    lambda s: s.value_counts().index[0]).to_dict()
subj_fac.update(tt_map)
for _sid, _fid in {"SUB0086": "FAC024", "SUB0087": "FAC025", "SUB0088": "FAC016",
                   "SUB0089": "FAC017", "SUB0090": "FAC018", "SUB0091": "FAC019",
                   "SUB0092": "FAC020"}.items():
    subj_fac.setdefault(_sid, _fid)
low_att = attendance[pd.to_numeric(attendance["attendance_percentage"]) < 75.0]
low_att = low_att.merge(subjects[["subject_id", "subject_name"]], on="subject_id", how="left")
for i, (_, r) in enumerate(low_att.head(60).iterrows()):
    pct = float(r["attendance_percentage"])
    pri = "High" if pct < 60 else "Medium"
    msg_rows.append({
        "message_id": str(uuid.uuid4()),
        "student_id": r["student_id"],
        "faculty_id": subj_fac.get(r["subject_id"], "FAC001"),
        "subject": r["subject_name"],
        "message_body": (f"Your attendance in {r['subject_name']} is currently {pct:.1f}%. "
                         f"Please ensure regular attendance to remain eligible for the end-semester examination."),
        "priority": pri,
        "status": "Sent",
        "created_at": "2026-08-26 13:14:53.000000+00:00",
        "message_type": "ATTENDANCE_ALERT",
        "title": "Attendance Alert",
        "event_id": "",
        "recipient_type": "STUDENT",
        "faculty_recipient_id": "",
    })
messages = pd.DataFrame(msg_rows, columns=messages.columns)
print("student_messages: generated", len(messages), "attendance alerts")

# ---------------------------------------------------------------------------
# 14. weekly_timetable : add BBA semester-5 timetable (fix missing coverage)
# ---------------------------------------------------------------------------
bba_map = {"SUB0086": "FAC024", "SUB0087": "FAC025", "SUB0088": "FAC016",
           "SUB0089": "FAC017", "SUB0090": "FAC018", "SUB0091": "FAC019",
           "SUB0092": "FAC020"}
bba_subs = [("Monday", "SUB0086", "Theory"), ("Monday", "SUB0087", "Theory"),
            ("Monday", "SUB0088", "Theory"),
            ("Tuesday", "SUB0089", "Theory"), ("Tuesday", "SUB0090", "Theory"),
            ("Tuesday", "SUB0091", "Laboratory"),
            ("Wednesday", "SUB0086", "Theory"), ("Wednesday", "SUB0092", "Project"),
            ("Wednesday", "SUB0087", "Theory"),
            ("Thursday", "SUB0088", "Theory"), ("Thursday", "SUB0089", "Theory"),
            ("Thursday", "SUB0090", "Theory"),
            ("Friday", "SUB0091", "Laboratory"), ("Friday", "SUB0092", "Project"),
            ("Friday", "SUB0087", "Theory")]
subj_name = dict(zip(subjects["subject_id"], subjects["subject_name"]))
next_id = int(timetable["timetable_id"].max()) + 1
rows = []
for k, (day, sid, ltype) in enumerate(bba_subs):
    slot = (k % 3) + 1
    start = "%02d:00:00" % (12 + slot)
    end = "%02d:00:00" % (13 + slot)
    rows.append({
        "timetable_id": next_id + k,
        "department_code": "2",
        "semester_no": "5",
        "academic_year": "2025-26",
        "day_name": day,
        "slot_no": slot,
        "start_time": start,
        "end_time": end,
        "subject_id": sid,
        "subject_name": subj_name[sid],
        "faculty_id": bba_map[sid],
        "lecture_type": ltype,
        "created_at": "2026-08-06 07:58:28.059023+00:00",
        "updated_at": "2026-08-26 13:14:53.456706+00:00",
    })
timetable = pd.concat([timetable, pd.DataFrame(rows)], ignore_index=True)
print("weekly_timetable: added", len(rows), "BBA sem-5 rows")

# ---------------------------------------------------------------------------
# write output
# ---------------------------------------------------------------------------
out = {
    "students.csv": students, "student_semester_summary.csv": summary,
    "student_subject_performance.csv": perf, "student_subject_enrollment.csv": enroll,
    "attendance.csv": attendance.drop(columns=["_att_pct"]),
    "faculty.csv": faculty, "subjects.csv": subjects, "faculty_student_map.csv": fsm,
    "users.csv": users, "student_goals.csv": goals, "student_messages.csv": messages,
    "weekly_timetable_07.csv": timetable, "ml_predictions.csv": ml_predictions,
    "risk_predictions.csv": risk_predictions, "prediction_feedback.csv": prediction_feedback,
    "departments.csv": load("departments.csv"), "career_preferences.csv": load("career_preferences.csv"),
    "career_preferences_v2.csv": load("career_preferences_v2.csv"),
    "lifestyle_survey.csv": load("lifestyle_survey.csv"),
    "student_lifestyle_survey.csv": load("student_lifestyle_survey.csv"),
    "attendance_weekly.csv": load("attendance_weekly.csv"),
    "student_learning_activity.csv": load("student_learning_activity.csv"),
    "daily_attendance_07.csv": load("daily_attendance_07.csv"),
    "student_skill_profile.csv": load("student_skill_profile.csv"),
    "student_messages.csv": messages,
    "attendance_change_log.csv": load("attendance_change_log.csv"),
    "performance_change_log.csv": load("performance_change_log.csv"),
    "placement.csv": load("placement.csv"),
    "risk_predictions.csv": risk_predictions,
}
# dedupe accidental double-keys
out = {k: v for k, v in out.items()}

for name, df in out.items():
    save(df, name)
    print("saved", name, df.shape)

print("\nALL DONE ->", DST)