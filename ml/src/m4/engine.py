"""M4 - Career Readiness Score Engine (Rule-based)."""
import pandas as pd
import numpy as np

class CareerReadinessEngine:
    """
    A deterministic, rule-based scoring engine for evaluating student career readiness.
    This is NOT an ML model and requires no training.
    """
    
    def __init__(self):
        self.version = "1.0"
        self.weights = {
            "academic_performance": 35,
            "growth_trend": 10,
            "career_preparedness": 25,
            "lifestyle_discipline": 30,
        }
        self.level_thresholds = {"High": 75, "Medium": 50}
        
        self.attendance_commitment_map = {
            "Poor": 2, "Average": 5, "Good": 7, "Very Good": 9, "Excellent": 10,
        }
        self.mental_wellbeing_map = {"Poor": 0, "Average": 2.5, "Good": 4, "Excellent": 5}
        self.stress_level_map = {"Very High": 0, "High": 1, "Medium": 3, "Low": 5}
        self.physical_activity_map = {"Never": 0, "Rare": 0.7, "Moderate": 1.4, "Regular": 2}

    @staticmethod
    def clip(x, lo, hi):
        return max(lo, min(hi, x))

    @staticmethod
    def scale(value, lo, hi, max_points):
        """Linearly map value in [lo, hi] to [0, max_points], clipped."""
        if hi == lo:
            return max_points / 2
        frac = (value - lo) / (hi - lo)
        frac = CareerReadinessEngine.clip(frac, 0.0, 1.0)
        return frac * max_points

    def aggregate_academic(self, sem_df: pd.DataFrame) -> pd.DataFrame:
        records = []
        for student_id, g in sem_df.sort_values("semester_no").groupby("student_id"):
            avg_pct = g["semester_percentage"].mean()
            avg_att = g["semester_attendance_percentage"].mean()
            total_backlogs_computed = g["backlog_count"].sum()
            num_sem = g["semester_no"].nunique()
            pass_ratio = (g["semester_result"] == "PASS").mean()

            if num_sem >= 2:
                slope = np.polyfit(g["semester_no"], g["semester_percentage"], 1)[0]
            else:
                slope = None

            first_pct = g["semester_percentage"].iloc[0]
            last_pct = g["semester_percentage"].iloc[-1]

            records.append({
                "student_id": student_id,
                "avg_semester_percentage": round(avg_pct, 2),
                "avg_semester_attendance": round(avg_att, 2),
                "total_backlogs_computed": int(total_backlogs_computed),
                "num_semesters_recorded": int(num_sem),
                "pass_ratio": round(pass_ratio, 2),
                "percentage_trend_slope": None if slope is None else round(slope, 3),
                "first_semester_percentage": round(first_pct, 2),
                "last_semester_percentage": round(last_pct, 2),
            })
        return pd.DataFrame(records)

    def score_academic_performance(self, row):
        pct_score = self.scale(row["avg_semester_percentage"], 40, 95, 20)
        att_score = self.scale(row["avg_semester_attendance"], 50, 95, 10)

        backlogs = row["total_backlogs_computed"]
        if backlogs == 0:
            backlog_score = 5
        elif backlogs <= 2:
            backlog_score = 3
        elif backlogs <= 4:
            backlog_score = 1
        else:
            backlog_score = 0

        total = round(pct_score + att_score + backlog_score, 2)
        return total, {
            "percentage_score_/20": round(pct_score, 2),
            "attendance_score_/10": round(att_score, 2),
            "backlog_score_/5": backlog_score,
        }

    def score_growth_trend(self, row):
        slope = row["percentage_trend_slope"]
        if slope is None or pd.isna(slope):
            return 5.0, "insufficient_history_neutral_score"
        trend_score = round(self.scale(slope, -2, 2, 10), 2)
        if slope > 0.5:
            note = "improving"
        elif slope < -0.5:
            note = "declining"
        else:
            note = "stable"
        return trend_score, note

    def score_career_preparedness(self, row):
        breakdown = {}
        internship_score = 15 if str(row["internship_completed"]).strip() == "Yes" else 0
        breakdown["internship_score_/15"] = internship_score

        has_cert_focus = pd.notna(row["certification_interest"]) and \
            str(row["certification_interest"]).strip() not in ("", "None", "NA", "nan")
        cert_score = 5 if has_cert_focus else 0
        breakdown["certification_focus_score_/5"] = cert_score

        plans_ahead = (str(row["higher_studies_interest"]).strip() == "Yes") or \
            (str(row["entrepreneurship_interest"]).strip() == "Yes")
        planning_score = 5 if plans_ahead else 0
        breakdown["forward_planning_score_/5"] = planning_score

        total = internship_score + cert_score + planning_score
        return float(total), breakdown

    def sleep_score(self, hours):
        if pd.isna(hours):
            return 0
        if 7 <= hours <= 9:
            return 3
        if 6 <= hours < 7 or 9 < hours <= 10:
            return 2
        if 5 <= hours < 6 or 10 < hours <= 11:
            return 1
        return 0

    def score_lifestyle_discipline(self, row):
        breakdown = {}
        study_score = round(self.scale(row["daily_study_hours"], 1, 6, 10), 2)
        breakdown["study_hours_score_/10"] = study_score

        att_commit_score = self.attendance_commitment_map.get(
            str(row["attendance_commitment"]).strip(), 5
        )
        breakdown["attendance_commitment_score_/10"] = att_commit_score

        mental_pts = self.mental_wellbeing_map.get(str(row["mental_wellbeing"]).strip(), 2.5)
        stress_pts = self.stress_level_map.get(str(row["stress_level"]).strip(), 3)
        wellbeing_score = round((mental_pts + stress_pts) / 2, 2)
        breakdown["wellbeing_score_/5"] = wellbeing_score

        sleep_pts = self.sleep_score(row["average_sleep_hours"])
        breakdown["sleep_score_/3"] = sleep_pts

        activity_pts = self.physical_activity_map.get(str(row["physical_activity"]).strip(), 1.4)
        breakdown["physical_activity_score_/2"] = activity_pts

        total = round(
            study_score + att_commit_score + wellbeing_score + sleep_pts + activity_pts, 2
        )
        return total, breakdown

    def compute_level(self, score):
        if score >= self.level_thresholds["High"]:
            return "High"
        if score >= self.level_thresholds["Medium"]:
            return "Medium"
        return "Low"

    def build_factors(self, academic_row, trend_note, life_row,
                      academic_breakdown, career_breakdown, lifestyle_breakdown):
        positives, risks = [], []

        if academic_breakdown["percentage_score_/20"] >= 16:
            positives.append(
                f"Strong academic record (avg {academic_row['avg_semester_percentage']}% across "
                f"{academic_row['num_semesters_recorded']} semesters)"
            )
        elif academic_breakdown["percentage_score_/20"] <= 8:
            risks.append(
                f"Low average academic percentage ({academic_row['avg_semester_percentage']}%)"
            )

        if academic_row["total_backlogs_computed"] == 0:
            positives.append("No academic backlogs recorded")
        elif academic_row["total_backlogs_computed"] >= 3:
            risks.append(f"{academic_row['total_backlogs_computed']} academic backlog(s) recorded")

        if academic_breakdown["attendance_score_/10"] <= 4:
            risks.append(
                f"Low average semester attendance ({academic_row['avg_semester_attendance']}%)"
            )

        if trend_note == "improving":
            positives.append(
                f"Improving academic trend (from {academic_row['first_semester_percentage']}% "
                f"to {academic_row['last_semester_percentage']}%)"
            )
        elif trend_note == "declining":
            risks.append(
                f"Declining academic trend (from {academic_row['first_semester_percentage']}% "
                f"to {academic_row['last_semester_percentage']}%)"
            )

        if career_breakdown["internship_score_/15"] == 15:
            positives.append("Has completed an internship")
        else:
            risks.append("No internship completed yet")

        if career_breakdown["forward_planning_score_/5"] == 5:
            positives.append(
                "Actively planning ahead (higher studies / entrepreneurship interest)"
            )

        if lifestyle_breakdown["study_hours_score_/10"] >= 8:
            positives.append(f"Strong daily study habit ({life_row['daily_study_hours']} hrs/day)")
        elif lifestyle_breakdown["study_hours_score_/10"] <= 3:
            risks.append(f"Low daily study hours ({life_row['daily_study_hours']} hrs/day)")

        if lifestyle_breakdown["wellbeing_score_/5"] <= 1.5:
            risks.append(
                f"Elevated stress / low wellbeing (stress: {life_row['stress_level']}, "
                f"wellbeing: {life_row['mental_wellbeing']})"
            )
        elif lifestyle_breakdown["wellbeing_score_/5"] >= 4:
            positives.append("Good mental wellbeing and low stress")

        if lifestyle_breakdown["attendance_commitment_score_/10"] <= 3:
            risks.append(f"Self-reported attendance commitment is '{life_row['attendance_commitment']}'")

        if lifestyle_breakdown["sleep_score_/3"] == 0:
            risks.append(f"Poor sleep pattern ({life_row['average_sleep_hours']} hrs/night)")

        if not positives:
            positives.append("No strong standout positive factors identified")
        if not risks:
            risks.append("No significant risk factors identified")

        return "; ".join(positives), "; ".join(risks)

    def score(self, students: pd.DataFrame, sem: pd.DataFrame, career: pd.DataFrame, lifestyle: pd.DataFrame) -> pd.DataFrame:
        """
        Executes the scoring pipeline.
        Returns a DataFrame containing scores, levels, and factors.
        """
        academic_agg = self.aggregate_academic(sem)

        df = students.merge(academic_agg, on="student_id", how="left")
        df = df.merge(career, on="student_id", how="left", suffixes=("", "_career"))
        df = df.merge(lifestyle, on="student_id", how="left", suffixes=("", "_life"))

        df = df.dropna(
            subset=["avg_semester_percentage", "internship_completed", "daily_study_hours"]
        ).reset_index(drop=True)

        results = []
        for _, row in df.iterrows():
            acad_score, acad_bd = self.score_academic_performance(row)
            trend_score, trend_note = self.score_growth_trend(row)
            career_score, career_bd = self.score_career_preparedness(row)
            life_score, life_bd = self.score_lifestyle_discipline(row)

            final_score = round(acad_score + trend_score + career_score + life_score, 2)
            final_score = self.clip(final_score, 0, 100)
            level = self.compute_level(final_score)

            positives, risks = self.build_factors(
                row, trend_note, row, acad_bd, career_bd, life_bd
            )

            results.append({
                "student_id": row["student_id"],
                "enrollment_no": row.get("enrollment_no", ""),
                "full_name": row.get("full_name", ""),
                "department_name": row.get("department_name", ""),
                "current_semester": row.get("current_semester", ""),

                "academic_performance_score_/35": acad_score,
                "academic_percentage_pts_/20": acad_bd["percentage_score_/20"],
                "academic_attendance_pts_/10": acad_bd["attendance_score_/10"],
                "academic_backlog_pts_/5": acad_bd["backlog_score_/5"],

                "growth_trend_score_/10": trend_score,
                "growth_trend_note": trend_note,

                "career_preparedness_score_/25": career_score,
                "internship_pts_/15": career_bd["internship_score_/15"],
                "certification_focus_pts_/5": career_bd["certification_focus_score_/5"],
                "forward_planning_pts_/5": career_bd["forward_planning_score_/5"],

                "lifestyle_discipline_score_/30": life_score,
                "study_hours_pts_/10": life_bd["study_hours_score_/10"],
                "attendance_commitment_pts_/10": life_bd["attendance_commitment_score_/10"],
                "wellbeing_pts_/5": life_bd["wellbeing_score_/5"],
                "sleep_pts_/3": life_bd["sleep_score_/3"],
                "physical_activity_pts_/2": life_bd["physical_activity_score_/2"],

                "avg_semester_percentage": row["avg_semester_percentage"],
                "avg_semester_attendance": row["avg_semester_attendance"],
                "total_backlogs_computed": row["total_backlogs_computed"],

                "career_readiness_score": final_score,
                "career_readiness_level": level,

                "positive_factors": positives,
                "risk_factors": risks,
            })

        out = pd.DataFrame(results).sort_values("career_readiness_score", ascending=False).reset_index(drop=True)
        return out
