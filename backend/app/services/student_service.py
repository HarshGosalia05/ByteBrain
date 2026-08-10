import math
import asyncpg
from datetime import date, datetime, timedelta, time
from typing import List, Optional
from app.core.config import settings
from app.repositories.student_repo import StudentRepository
from app.schemas.student import (
    StudentProfile,
    AcademicOverview,
    SemesterSummaryResponse,
    SubjectPerformanceResponse,
)
from app.schemas.student_analytics import (
    AttemptHistoryItem,
    AttendanceWhatIfContext,
    AttendanceWhatIfResponse,
    AttendanceWhatIfSimulation,
    AttendanceWhatIfSubject,
    BenchmarkItem,
    LearningGapItem,
    NeedsAttentionItem,
    PerformanceTrends,
    StrengthItem,
    StudentAnalyticsResponse,
    WhatIfResponse,
)
from app.schemas.student_daily import (
    AttendanceContext,
    ClassCountByDay,
    DailyAssistantResponse,
    DailyClass,
    DailyPriority,
    Deferral,
    FreeSlot,
    NextClass,
    StudentTimetableDay,
    StudentTimetableResponse,
    StudentTimetableSession,
    StudentTimetableSlot,
    StudyPriority,
    TermContext,
    UpcomingDay,
)
from app.services.student_analytics_rules import (
    compute_attendance_what_if,
    compute_attempt_history,
    compute_benchmark,
    compute_learning_gaps,
    compute_needs_attention,
    compute_strengths,
    compute_trends,
)
from app.services.faculty_service import derive_marks_fields
from fastapi import HTTPException, status


class StudentService:
    def __init__(self, pool: asyncpg.Pool):
        self.repo = StudentRepository(pool)

    async def get_profile(self, student_id: str) -> StudentProfile:
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )
        return StudentProfile(**profile_data)

    async def get_academic_summary(self, student_id: str) -> SemesterSummaryResponse:
        # Check if student exists first
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        summaries = await self.repo.get_semester_summaries(student_id)
        overview = AcademicOverview(
            current_semester=profile_data.get("current_semester"),
            current_academic_year=profile_data.get("current_academic_year"),
            latest_sgpa=profile_data.get("latest_sgpa"),
            overall_cgpa=profile_data.get("overall_cgpa"),
            overall_percentage=profile_data.get("overall_percentage"),
            total_credits_registered=profile_data.get("total_credits_registered"),
            total_credits_earned=profile_data.get("total_credits_earned"),
            total_backlogs=profile_data.get("total_backlogs"),
            academic_standing=profile_data.get("academic_standing"),
        )
        return SemesterSummaryResponse(
            student_id=student_id,
            overview=overview,
            summaries=summaries,
        )

    async def get_performance(
        self, student_id: str, semester: Optional[int] = None
    ) -> SubjectPerformanceResponse:
        # Check if student exists first
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        performance = await self.repo.get_subject_performance(student_id, semester)
        return SubjectPerformanceResponse(
            student_id=student_id,
            performance=performance,
        )

    async def get_analytics(self, student_id: str) -> StudentAnalyticsResponse:
        """MD-03 deterministic performance analytics (read-only, no writes)."""
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        summaries = await self.repo.get_semester_summaries(student_id)
        performance = await self.repo.get_subject_performance(student_id)

        subject_ids = sorted(
            {row["subject_id"] for row in performance if row.get("percentage") is not None}
        )
        department_code = profile_data.get("department_code")
        class_averages = []
        if subject_ids and department_code:
            class_averages = await self.repo.get_class_benchmark_averages(
                department_code, student_id, subject_ids
            )

        return StudentAnalyticsResponse(
            student_id=student_id,
            trends=PerformanceTrends(**compute_trends(summaries)),
            strengths=[StrengthItem(**item) for item in compute_strengths(performance)],
            needs_attention=[
                NeedsAttentionItem(**item) for item in compute_needs_attention(performance)
            ],
            learning_gaps=[
                LearningGapItem(**item) for item in compute_learning_gaps(performance)
            ],
            class_benchmark=[
                BenchmarkItem(**item) for item in compute_benchmark(performance, class_averages)
            ],
            attempt_history=[
                AttemptHistoryItem(**item) for item in compute_attempt_history(performance)
            ],
        )

    @staticmethod
    def _resolve_day_name(recorded: Optional[str], focus_date: date) -> str:
        """Recorded day label wins when the institution has one; else weekday."""
        return recorded if recorded else focus_date.strftime("%A")

    @staticmethod
    def _day_order(day_name: str) -> int:
        order = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }
        return order.get(day_name, 99)

    async def get_timetable(self, student_id: str) -> StudentTimetableResponse:
        """MD-04 weekly timetable stitched from the student's current term.

        Timetable stitching keys: department_code + current semester + current
        academic year prefix (short/long year formats differ between tables).
        """
        context = await self.repo.get_student_term_context(student_id)
        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        year_prefix = (context.get("current_academic_year") or "")[:4]
        data = await self.repo.get_student_timetable(
            context["department_code"], context["current_semester"], year_prefix
        )
        rows = data["sessions"]
        slots = data["slots"]
        resolved_year = rows[0]["academic_year"] if rows else (context.get("current_academic_year") or "")

        grouped: dict = {}
        for r in sorted(
            rows,
            key=lambda row: (
                self._day_order(row["day_name"]),
                row["slot_no"],
                str(row["start_time"]),
            ),
        ):
            grouped.setdefault(r["day_name"], []).append(StudentTimetableSession(**r))

        return StudentTimetableResponse(
            student_id=student_id,
            semester_no=context["current_semester"],
            academic_year=resolved_year,
            department_name=context.get("department_name"),
            total_sessions=len(rows),
            slots=[StudentTimetableSlot(**slot) for slot in slots],
            days=[
                StudentTimetableDay(day_name=day, sessions=sessions)
                for day, sessions in grouped.items()
            ],
        )

    async def get_daily_assistant(
        self, student_id: str, focus_date_str: Optional[str] = None
    ) -> DailyAssistantResponse:
        """MD-04 deterministic daily assistant (read-only).

        Computes today's classes, next class, free slots, and study priorities
        from canonical timetable + aggregate attendance + performance. Lecture
        history is only ever shown as recorded rows â€” missing daily records are
        never inferred as absence.
        """
        context = await self.repo.get_student_term_context(student_id)
        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        try:
            focus_date = date.fromisoformat(focus_date_str) if focus_date_str else date.today()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date must be a valid YYYY-MM-DD value",
            )
        is_focus_today = focus_date == date.today()

        recorded_day = await self.repo.get_recorded_day_name(
            student_id, focus_date
        )
        day_name = self._resolve_day_name(recorded_day, focus_date)
        day_source = "recorded" if recorded_day else "calendar"

        year_prefix = (context.get("current_academic_year") or "")[:4]
        tmt = await self.repo.get_student_timetable(
            context["department_code"], context["current_semester"], year_prefix
        )
        rows = tmt["sessions"]
        slots = tmt["slots"]
        resolved_year = rows[0]["academic_year"] if rows else (context.get("current_academic_year") or "")

        by_day: dict = {}
        for r in rows:
            by_day.setdefault(r["day_name"], []).append(r)

        attendance = await self.repo.get_semester_attendance(
            student_id, context["current_semester"]
        )
        att_by_subject = {a["subject_id"]: a for a in attendance}

        today_sessions = sorted(
            by_day.get(day_name, []),
            key=lambda r: (r["slot_no"], str(r["start_time"])),
        )

        statuses: dict = {}
        if today_sessions:
            recorded = await self.repo.get_daily_statuses(
                student_id,
                focus_date,
                [s["subject_id"] for s in today_sessions],
            )
            for r in recorded:
                statuses.setdefault(r["subject_id"], []).append(r["attendance_status"])

        daily_classes = []
        for s in today_sessions:
            a = att_by_subject.get(s["subject_id"]) or {}
            daily_classes.append(
                DailyClass(
                    subject_id=s["subject_id"],
                    subject_code=s.get("subject_code"),
                    subject_name=s["subject_name"],
                    slot_no=s["slot_no"],
                    start_time=s["start_time"],
                    end_time=s["end_time"],
                    lecture_type=s.get("lecture_type"),
                    credits=s.get("credits"),
                    faculty_name=s.get("faculty_name"),
                    attendance_percentage=a.get("attendance_percentage"),
                    attendance_status=a.get("attendance_status"),
                    eligibility_status=a.get("eligibility_status"),
                    shortage_flag=a.get("shortage_flag"),
                    performance_percentage=a.get("performance_percentage"),
                    recorded_statuses=statuses.get(s["subject_id"], []),
                    recorded=bool(statuses.get(s["subject_id"])),
                )
            )

        occupied_slots = {s["slot_no"] for s in today_sessions}
        free_slots = [
            FreeSlot(**slot) for slot in slots if slot["slot_no"] not in occupied_slots
        ]

        next_class = None
        if is_focus_today:
            now = datetime.now().time()
            upcoming = [s for s in today_sessions if s["start_time"] > now]
            if upcoming:
                nxt = upcoming[0]
                a = att_by_subject.get(nxt["subject_id"]) or {}
                next_class = NextClass(
                    day_name=day_name,
                    is_tomorrow=False,
                    subject_id=nxt["subject_id"],
                    subject_code=nxt.get("subject_code"),
                    subject_name=nxt["subject_name"],
                    slot_no=nxt["slot_no"],
                    start_time=nxt["start_time"],
                    end_time=nxt["end_time"],
                    attendance_percentage=a.get("attendance_percentage"),
                )
            else:
                tomorrow_date = focus_date + timedelta(days=1)
                tmr_recorded = await self.repo.get_recorded_day_name(
                    student_id, tomorrow_date
                )
                tmr_day = self._resolve_day_name(tmr_recorded, tomorrow_date)
                tmr_sessions = sorted(
                    by_day.get(tmr_day, []),
                    key=lambda r: (r["slot_no"], str(r["start_time"])),
                )
                if tmr_sessions:
                    nxt = tmr_sessions[0]
                    a = att_by_subject.get(nxt["subject_id"]) or {}
                    next_class = NextClass(
                        day_name=tmr_day,
                        is_tomorrow=True,
                        subject_id=nxt["subject_id"],
                        subject_code=nxt.get("subject_code"),
                        subject_name=nxt["subject_name"],
                        slot_no=nxt["slot_no"],
                        start_time=nxt["start_time"],
                        end_time=nxt["end_time"],
                        attendance_percentage=a.get("attendance_percentage"),
                    )
        elif today_sessions:
            nxt = today_sessions[0]
            a = att_by_subject.get(nxt["subject_id"]) or {}
            next_class = NextClass(
                day_name=day_name,
                is_tomorrow=False,
                subject_id=nxt["subject_id"],
                subject_code=nxt.get("subject_code"),
                subject_name=nxt["subject_name"],
                slot_no=nxt["slot_no"],
                start_time=nxt["start_time"],
                end_time=nxt["end_time"],
                attendance_percentage=a.get("attendance_percentage"),
            )

        classes_per_day = [
            ClassCountByDay(day_name=day, count=len(sessions))
            for day, sessions in sorted(
                by_day.items(), key=lambda item: self._day_order(item[0])
            )
        ]

        attendance_threshold = settings.FACULTY_ATTENDANCE_THRESHOLD
        attendance_critical = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
        attendance_good_split = settings.ATTENDANCE_STATUS_GOOD_SPLIT
        performance_threshold = settings.FACULTY_PERFORMANCE_THRESHOLD
        performance_critical = settings.CRITICAL_PERFORMANCE_THRESHOLD

        study_priorities = []
        for a in attendance:
            att_pct = a.get("attendance_percentage")
            perf_pct = a.get("performance_percentage")
            reasons: List[str] = []
            if att_pct is not None and att_pct < attendance_threshold:
                reasons.append(
                    f"Attendance is below the {attendance_threshold:.0f}% target"
                )
            if att_pct is not None and att_pct < attendance_critical:
                reasons.append(
                    f"Attendance is critically below {attendance_critical:.0f}%"
                )
            if a.get("shortage_flag") == "Yes":
                reasons.append("Attendance shortage flagged")
            if a.get("eligibility_status") == "Not Eligible":
                reasons.append("Not eligible to appear for exams at current attendance")
            if perf_pct is not None and perf_pct < performance_threshold:
                reasons.append(f"Performance is below {performance_threshold:.0f}%")
            if perf_pct is not None and perf_pct < performance_critical:
                reasons.append("Performance is critically low")
            if not reasons:
                continue

            if (att_pct is not None and att_pct < attendance_critical) or (
                perf_pct is not None and perf_pct < performance_critical
            ):
                priority, priority_label = 1, "Critical"
            elif (
                (att_pct is not None and att_pct < attendance_threshold)
                or (perf_pct is not None and perf_pct < performance_threshold)
                or a.get("shortage_flag") == "Yes"
                or a.get("eligibility_status") == "Not Eligible"
            ):
                priority, priority_label = 2, "At risk"
            else:
                priority, priority_label = 3, "Watch"

            required = None
            if att_pct is not None and att_pct < attendance_threshold:
                total = a.get("total_classes")
                attended = a.get("attended_classes")
                if (
                    total is not None
                    and attended is not None
                    and total > attended
                ):
                    target = attendance_threshold / 100.0
                    required = max(1, math.ceil((target * total - attended) / (1 - target)))

            study_priorities.append(
                StudyPriority(
                    priority=priority,
                    priority_label=priority_label,
                    subject_id=a["subject_id"],
                    subject_code=a.get("subject_code"),
                    subject_name=a["subject_name"],
                    attendance_percentage=att_pct,
                    performance_percentage=perf_pct,
                    shortage_flag=a.get("shortage_flag"),
                    eligibility_status=a.get("eligibility_status"),
                    reasons=reasons,
                    required_classes_to_reach_target=required,
                    target_attendance=attendance_threshold,
                )
            )
        study_priorities.sort(
            key=lambda p: (
                p.priority,
                p.attendance_percentage if p.attendance_percentage is not None else 0,
                p.performance_percentage if p.performance_percentage is not None else 0,
            )
        )

        daily_priorities = []
        idx = 1
        if next_class:
            subj = att_by_subject.get(next_class.subject_id)
            if (
                subj
                and subj.get("attendance_percentage") is not None
                and subj["attendance_percentage"] < attendance_threshold
            ):
                daily_priorities.append(
                    DailyPriority(
                        priority=idx,
                        text=(
                            f"Prepare for {next_class.subject_name} â€” attendance is "
                            f"{subj['attendance_percentage']:.1f}%."
                        ),
                    )
                )
                idx += 1
        for p in study_priorities[:2]:
            if p.required_classes_to_reach_target is not None:
                daily_priorities.append(
                    DailyPriority(
                        priority=idx,
                        text=(
                            f"{p.subject_name}: attend the next "
                            f"{p.required_classes_to_reach_target} classes to reach the "
                            f"{p.target_attendance:.0f}% target."
                        ),
                    )
                )
            else:
                main_reason = p.reasons[0] if p.reasons else "needs attention"
                daily_priorities.append(
                    DailyPriority(priority=idx, text=f"{p.subject_name}: {main_reason}.")
                )
            idx += 1
        if free_slots and study_priorities:
            top = study_priorities[0]
            slot = free_slots[0]
            daily_priorities.append(
                DailyPriority(
                    priority=idx,
                    text=(
                        f"Use your free slot {slot.start_time.strftime('%H:%M')}â€“"
                        f"{slot.end_time.strftime('%H:%M')} to revise {top.subject_name}."
                    ),
                )
            )
            idx += 1
        elif not study_priorities and daily_classes:
            daily_priorities.append(
                DailyPriority(
                    priority=idx,
                    text="You're on track â€” keep attending classes to maintain your standing.",
                )
            )
            idx += 1
        if not daily_classes and idx == 1:
            daily_priorities.append(
                DailyPriority(priority=idx, text="No classes are scheduled for today.")
            )

        upcoming_classes = []
        for offset in (1, 2):
            probe_date = focus_date + timedelta(days=offset)
            probe_recorded = await self.repo.get_recorded_day_name(
                student_id, probe_date
            )
            probe_day = self._resolve_day_name(probe_recorded, probe_date)
            sessions = sorted(
                by_day.get(probe_day, []),
                key=lambda r: (r["slot_no"], str(r["start_time"])),
            )
            upcoming_classes.append(
                UpcomingDay(
                    day_name=probe_day,
                    is_tomorrow=offset == 1,
                    sessions=[StudentTimetableSession(**s) for s in sessions],
                )
            )

        total_classes = sum(
            a["total_classes"] or 0 for a in attendance if a.get("total_classes") is not None
        )
        attended_classes = sum(
            a["attended_classes"] or 0 for a in attendance if a.get("attended_classes") is not None
        )
        semester_overall = (
            round((attended_classes / total_classes) * 100, 2) if total_classes else None
        )

        attendance_context = AttendanceContext(
            semester_overall_attendance=semester_overall,
            stored_overall_attendance=context.get("overall_attendance_percentage"),
            note=(
                "Overall attendance is derived from stored aggregates. "
                "Lecture-level history may be partial and is never used to infer absence."
            ),
        )

        deferrals = [
            Deferral(
                feature="Assignments / submissions",
                status="not_verified",
                note="No assignment or submission tables exist in the repository yet.",
            ),
            Deferral(
                feature="Exam reminders",
                status="not_verified",
                note="No examination table exists in the repository yet.",
            ),
        ]

        return DailyAssistantResponse(
            student_id=student_id,
            date=focus_date,
            day_name=day_name,
            day_source=day_source,
            is_focus_today=is_focus_today,
            term=TermContext(
                semester_no=context["current_semester"],
                academic_year=resolved_year,
                department_name=context.get("department_name"),
                timetable_available=bool(rows),
            ),
            today_classes=daily_classes,
            next_class=next_class,
            free_slots=free_slots,
            classes_per_day=classes_per_day,
            study_priorities=study_priorities,
            daily_priorities=daily_priorities,
            upcoming_classes=upcoming_classes,
            attendance_context=attendance_context,
            deferrals=deferrals,
        )

    def simulate_marks(
        self,
        internal_marks: Optional[int],
        mid_sem_marks: Optional[int],
        end_sem_marks: Optional[int],
    ) -> WhatIfResponse:
        """MD-03 marks simulator.

        Purely a simulation â€” reuses the exact canonical derivation used by
        Faculty (``derive_marks_fields``) and never touches the database.

        Defense in depth: the API layer already constrains the query params,
        and each component is re-validated here so an invalid value can never
        reach the canonical derivation.
        """
        bounds = [
            ("internal_marks", internal_marks, settings.MARKS_INTERNAL_MAX),
            ("mid_sem_marks", mid_sem_marks, settings.MARKS_MID_SEM_MAX),
            ("end_sem_marks", end_sem_marks, settings.MARKS_END_SEM_MAX),
        ]
        for name, value, hi in bounds:
            if value is None:
                continue
            if type(value) is not int or not (0 <= value <= hi):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{name} must be an integer between 0 and {hi}",
                )
        derived = derive_marks_fields(internal_marks, mid_sem_marks, end_sem_marks)
        complete = all(
            value is not None for value in (internal_marks, mid_sem_marks, end_sem_marks)
        )
        return WhatIfResponse(
            internal_marks=internal_marks,
            mid_sem_marks=mid_sem_marks,
            end_sem_marks=end_sem_marks,
            complete=complete,
            total_marks=derived["total_marks"],
            percentage=derived["percentage"],
            grade=derived["grade"],
            grade_point=derived["grade_point"],
            result_status=derived["result_status"],
            performance_category=derived["performance_category"],
        )

    async def simulate_attendance(
        self,
        student_id: str,
        subject_id: Optional[str] = None,
        hypothetical_present: int = 0,
        hypothetical_absent: int = 0,
    ) -> AttendanceWhatIfResponse:
        """MD-04 attendance what-if simulator (read-only, never writes).

        Loads the authoritative per-subject attendance baseline for the
        student's current semester and projects an attendance percentage from
        the pure ``compute_attendance_what_if`` rule. When no ``subject_id`` is
        given the response carries just the baseline context that powers the
        client-side simulator.
        """
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        current_semester = profile_data.get("current_semester")
        attendance = (
            await self.repo.get_semester_attendance(student_id, current_semester)
            if current_semester
            else []
        )

        target = settings.FACULTY_ATTENDANCE_THRESHOLD

        subjects = []
        for row in attendance:
            total = row.get("total_classes")
            attended = row.get("attended_classes")
            pct = row.get("attendance_percentage")
            if total is not None and attended is not None and total > 0:
                pct = round(attended / total * 100, 2)
            subjects.append(
                AttendanceWhatIfSubject(
                    subject_id=row["subject_id"],
                    subject_code=row.get("subject_code"),
                    subject_name=row["subject_name"],
                    credits=row.get("credits"),
                    total_classes=total,
                    attended_classes=attended,
                    attendance_percentage=pct,
                    attendance_status=row.get("attendance_status"),
                    eligibility_status=row.get("eligibility_status"),
                    shortage_flag=row.get("shortage_flag"),
                )
            )
        subjects.sort(key=lambda s: s.subject_name)

        simulation = None
        if subject_id:
            baseline = next(
                (row for row in attendance if row["subject_id"] == subject_id),
                None,
            )
            if baseline is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subject not found in your current semester",
                )
            derived = compute_attendance_what_if(
                int(baseline.get("total_classes") or 0),
                int(baseline.get("attended_classes") or 0),
                hypothetical_present,
                hypothetical_absent,
                target,
            )
            simulation = AttendanceWhatIfSimulation(
                subject_id=baseline["subject_id"],
                subject_code=baseline.get("subject_code"),
                subject_name=baseline["subject_name"],
                **derived,
            )

        return AttendanceWhatIfResponse(
            student_id=student_id,
            context=AttendanceWhatIfContext(
                student_id=student_id,
                target_attendance=target,
                subjects=subjects,
            ),
            simulation=simulation,
        )
