"""MD-05 notification rules — pure, deterministic transforms.

Every function here is a pure rule (no ML, no GenAI, no DB access). They turn
event descriptors produced by the faculty write paths into rows for
``student_messages``.

Notification categories (planned MD-05 categories; each maps to
``student_messages.message_type``):

    MARKS_PUBLISHED      first time marks are published for a subject /
                         end-semester final result published.
    MARKS_UPDATED        an already-published mark is changed.
    ATTENDANCE_WARNING   aggregate attendance crosses below the target or
                         critical threshold for a subject.
    ELIGIBILITY_WARNING  attendance drops so the student becomes not eligible
                         for the examination.
    RISK_ALERT           risk prediction raised for the student.
    TIMETABLE_CHANGE     timetable session changes (added/moved/removed).
    PERFORMANCE_CHANGE   meaningful result/grade improvement or decline.

Faculty recipients use their own types on the same store:

    STUDENT_ATTENDANCE_WARNING   a student's attendance in one of the
                                 faculty member's subjects crossed below the
                                 target or critical threshold.
    STUDENT_ELIGIBILITY_WARNING  a student became not eligible to appear for
                                 the examination in a faculty subject.
    STUDENT_PERFORMANCE_CHANGE   a student's final result in a faculty subject
                                 is a Fail.

Deduplication: every notification carries an ``event_id`` that is a pure
function of the underlying event (e.g. ``perf-change:{change_id}``,
``att-cross:{student}:{subject}:{semester}:{direction}``,
``fac-perf-fail:{faculty}:{change_id}``). The repository inserts rows with
``ON CONFLICT`` against the per-recipient partial unique index
(student_id, event_id) or (faculty_recipient_id, event_id), so the same event
can never produce two notifications for the same recipient.

Trend-based signals (repeated low performance, declining performance, backlog)
are intentionally surfaced through the dashboard priorities rather than pushed
as notifications, so the inbox only ever carries deterministic, event-driven
alerts. RISK_ALERT and TIMETABLE_CHANGE builders exist (and are unit-tested)
but are currently unreachable — risk_predictions has no writer and the
timetable has no edit endpoint. They are intentionally not invoked by any
write path and are reported as limitations rather than fabricated.
"""

from typing import Any, Dict, List, Optional

NOTIFICATION_TYPE_SYSTEM = "SYSTEM"
NOTIFICATION_TYPE_FACULTY_MESSAGE = "FACULTY_MESSAGE"

NOTIFICATION_TYPES_MD05 = [
    "MARKS_PUBLISHED",
    "MARKS_UPDATED",
    "ATTENDANCE_WARNING",
    "ELIGIBILITY_WARNING",
    "RISK_ALERT",
    "TIMETABLE_CHANGE",
    "PERFORMANCE_CHANGE",
]

NOTIFICATION_TYPES_FACULTY = [
    "STUDENT_ATTENDANCE_WARNING",
    "STUDENT_ELIGIBILITY_WARNING",
    "STUDENT_PERFORMANCE_CHANGE",
    "SYSTEM",
    "FACULTY_MESSAGE",
]

DEFAULT_PRIORITY = "Normal"
HIGH_PRIORITY = "High"


def perf_change_event_id(change_id: Any) -> str:
    return f"perf-change:{change_id}"


def perf_fail_event_id(change_id: Any) -> str:
    return f"perf-fail:{change_id}"


def att_crossing_event_id(
    student_id: str, subject_id: str, semester_no: int, direction: str
) -> str:
    return f"att-cross:{student_id}:{subject_id}:{semester_no}:{direction}"


def eligibility_event_id(student_id: str, semester_no: int) -> str:
    return f"elig:{student_id}:{semester_no}:Not Eligible"


def faculty_att_crossing_event_id(
    faculty_id: str, student_id: str, subject_id: str, semester_no: int, direction: str
) -> str:
    return f"fac-att-cross:{faculty_id}:{student_id}:{subject_id}:{semester_no}:{direction}"


def faculty_eligibility_event_id(faculty_id: str, student_id: str, semester_no: int) -> str:
    return f"fac-elig:{faculty_id}:{student_id}:{semester_no}:Not Eligible"


def faculty_perf_fail_event_id(faculty_id: str, change_id: Any) -> str:
    return f"fac-perf-fail:{faculty_id}:{change_id}"


_FIELD_LABELS = {
    "internal_marks": "internal",
    "mid_sem_marks": "mid-semester",
    "end_sem_marks": "end-semester",
}


def build_performance_notifications(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Marks events -> notification rows.

    Two event kinds are accepted (the faculty write path decides which):

    * ``publish`` — first-time marks entry for a subject. Exactly one
      MARKS_PUBLISHED notification is produced (not one per component) so a
      fully-entered row does not spam the student.
        keys: kind='publish', student_id, subject_id, subject_name,
              change_id, fields=[{name, value}, ...]
    * ``field`` — a single component changed on an existing row.
        keys: kind='field', student_id, subject_id, subject_name,
              field_name, old_value, new_value, change_id
      Rules: end-semester NULL -> value is a MARKS_PUBLISHED (final result);
      any other non-NULL change is a MARKS_UPDATED; clearing (new_value is
      None) is skipped as it is a correction, not a student-facing event.
    """
    notifications: List[Dict[str, Any]] = []
    for event in events:
        if event.get("kind") == "publish":
            notifications.append(_publish_event(event))
            continue
        if event.get("kind") == "field":
            entry = _field_event(event)
            if entry is not None:
                notifications.append(entry)
    return notifications


def _publish_event(event: Dict[str, Any]) -> Dict[str, Any]:
    subject = event["subject_name"]
    fields = event.get("fields") or []
    present = [
        (f["name"], f["value"]) for f in fields if f.get("value") is not None
    ]
    if present:
        detail = ", ".join(
            f"{_FIELD_LABELS.get(name, name)} {value}" for name, value in present
        )
        body = f"Your marks for {subject} are now available ({detail})."
    else:
        body = f"Marks for {subject} have been published."
    return {
        "student_id": event["student_id"],
        "faculty_id": None,
        "subject": subject,
        "message_type": "MARKS_PUBLISHED",
        "title": f"{subject} marks published",
        "message_body": body,
        "priority": DEFAULT_PRIORITY,
        "event_id": perf_change_event_id(event["change_id"]),
    }


def _field_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    field = event.get("field_name")
    old_value = event.get("old_value")
    new_value = event.get("new_value")
    subject = event["subject_name"]

    if new_value is None:
        return None
    if field == "end_sem_marks" and old_value is None:
        return {
            "student_id": event["student_id"],
            "faculty_id": None,
            "subject": subject,
            "message_type": "MARKS_PUBLISHED",
            "title": f"Final result published for {subject}",
            "message_body": (
                f"Your end-semester marks in {subject} have been published ({new_value})."
            ),
            "priority": DEFAULT_PRIORITY,
            "event_id": perf_change_event_id(event["change_id"]),
        }

    label = _FIELD_LABELS.get(field, field)
    return {
        "student_id": event["student_id"],
        "faculty_id": None,
        "subject": subject,
        "message_type": "MARKS_UPDATED",
        "title": f"{subject} marks updated",
        "message_body": (
            f"Your {label} marks in {subject} were updated "
            f"from {old_value} to {new_value}."
        ),
        "priority": DEFAULT_PRIORITY,
        "event_id": perf_change_event_id(event["change_id"]),
    }


def build_performance_change_notifications(
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Fail-result events -> PERFORMANCE_CHANGE rows (student recipient).

    Accepts the same event descriptors as ``build_performance_notifications``
    plus the derived ``result_status``/``percentage`` of the row as written.
    A PERFORMANCE_CHANGE is produced only when a result *completes* as Fail:
    either a freshly published row (kind='publish') whose result is Fail, or a
    field event that first enters end-semester marks (old None -> value) with a
    Fail result. Re-edits of an already-failed row are intentionally skipped so
    the inbox does not re-alert on every correction.

    Event identity is ``perf-fail:{change_id}`` (the same audit change_id used
    by MARKS_PUBLISHED, prefixed differently), so re-processing the same event
    can never duplicate the notification.
    """
    notifications: List[Dict[str, Any]] = []
    for event in events:
        if event.get("result_status") != "Fail":
            continue
        if event.get("kind") == "field":
            if event.get("field_name") != "end_sem_marks":
                continue
            if event.get("old_value") is not None or event.get("new_value") is None:
                continue
        subject = event["subject_name"]
        notifications.append(
            {
                "student_id": event["student_id"],
                "faculty_id": None,
                "subject": subject,
                "message_type": "PERFORMANCE_CHANGE",
                "title": f"Fail result in {subject}",
                "message_body": (
                    f"Your result in {subject} is a Fail. Review the marks "
                    f"and plan a retake to clear the backlog."
                ),
                "priority": HIGH_PRIORITY,
                "event_id": perf_fail_event_id(event["change_id"]),
            }
        )
    return notifications


def build_faculty_attendance_warnings(
    crossings: List[Dict[str, Any]],
    flips: List[Dict[str, Any]],
    faculty_id: str,
    below_target_threshold: float,
    critical_threshold: float,
) -> List[Dict[str, Any]]:
    """Attendance crossings/flips -> faculty notification rows.

    Each crossing: student_id, student_name, subject_id, subject_name,
    semester_no, old_pct, new_pct, direction. Each flip: student_id,
    student_name, subject_id, subject_name, semester_no. Recipient is the
    owning faculty member; event identity is per faculty member so the same
    event addressed to different faculty members stays distinct.
    """
    notifications: List[Dict[str, Any]] = []
    for crossing in crossings:
        direction = crossing["direction"]
        subject = crossing["subject_name"]
        student = crossing.get("student_name") or crossing["student_id"]
        new_pct = crossing["new_pct"]
        old_pct = crossing["old_pct"]
        if direction == "below-critical":
            title = f"Attendance critically low: {student}"
            body = (
                f"{student}'s attendance in {subject} dropped to {new_pct:.1f}% "
                f"(from {old_pct:.1f}%), below the critical {critical_threshold:.0f}% level."
            )
            priority = HIGH_PRIORITY
        else:
            title = f"Attendance below target: {student}"
            body = (
                f"{student}'s attendance in {subject} dropped below the "
                f"{below_target_threshold:.0f}% target to {new_pct:.1f}% "
                f"(from {old_pct:.1f}%)."
            )
            priority = DEFAULT_PRIORITY
        notifications.append(
            {
                "recipient_type": "faculty",
                "faculty_recipient_id": faculty_id,
                "student_id": None,
                "faculty_id": None,
                "subject": subject,
                "message_type": "STUDENT_ATTENDANCE_WARNING",
                "title": title,
                "message_body": body,
                "priority": priority,
                "event_id": faculty_att_crossing_event_id(
                    faculty_id,
                    crossing["student_id"],
                    crossing["subject_id"],
                    crossing["semester_no"],
                    direction,
                ),
            }
        )
    for flip in flips:
        student = flip.get("student_name") or flip["student_id"]
        subject = flip["subject_name"]
        notifications.append(
            {
                "recipient_type": "faculty",
                "faculty_recipient_id": faculty_id,
                "student_id": None,
                "faculty_id": None,
                "subject": subject,
                "message_type": "STUDENT_ELIGIBILITY_WARNING",
                "title": f"Exam eligibility at risk: {student}",
                "message_body": (
                    f"{student}'s attendance in {subject} is now below the eligibility "
                    f"requirement for semester {flip['semester_no']}. They are not "
                    f"currently eligible to appear for the examination."
                ),
                "priority": HIGH_PRIORITY,
                "event_id": faculty_eligibility_event_id(
                    faculty_id, flip["student_id"], flip["semester_no"]
                ),
            }
        )
    return notifications


def build_faculty_performance_notifications(
    events: List[Dict[str, Any]],
    faculty_id: str,
) -> List[Dict[str, Any]]:
    """Fail-result events -> STUDENT_PERFORMANCE_CHANGE rows (faculty recipient).

    Mirrors ``build_performance_change_notifications`` conditions but addresses
    the subject's owning faculty member instead of the student. Each event must
    carry student_id, student_name, subject_name, result_status, change_id.
    """
    notifications: List[Dict[str, Any]] = []
    for event in events:
        if event.get("result_status") != "Fail":
            continue
        if event.get("kind") == "field":
            if event.get("field_name") != "end_sem_marks":
                continue
            if event.get("old_value") is not None or event.get("new_value") is None:
                continue
        student = event.get("student_name") or event["student_id"]
        subject = event["subject_name"]
        percentage = event.get("percentage")
        detail = f" ({percentage:.1f}%)" if percentage is not None else ""
        notifications.append(
            {
                "recipient_type": "faculty",
                "faculty_recipient_id": faculty_id,
                "student_id": None,
                "faculty_id": None,
                "subject": subject,
                "message_type": "STUDENT_PERFORMANCE_CHANGE",
                "title": f"Fail result: {student}",
                "message_body": (
                    f"The result of {student} in {subject} is a Fail{detail}. "
                    f"Consider a review session or a retake plan."
                ),
                "priority": HIGH_PRIORITY,
                "event_id": faculty_perf_fail_event_id(faculty_id, event["change_id"]),
            }
        )
    return notifications


def build_attendance_warnings(
    crossings: List[Dict[str, Any]],
    below_target_threshold: float,
    critical_threshold: float,
) -> List[Dict[str, Any]]:
    """Attendance threshold crossings -> ATTENDANCE_WARNING rows.

    Each crossing: student_id, subject_id, subject_name, semester_no,
    old_pct, new_pct, direction ('below-target' | 'below-critical').
    Direction is part of the event identity so a recovery + re-crossing within
    a semester is still deduplicated (at most one warning per direction).
    """
    notifications: List[Dict[str, Any]] = []
    for crossing in crossings:
        direction = crossing["direction"]
        subject = crossing["subject_name"]
        new_pct = crossing["new_pct"]
        old_pct = crossing["old_pct"]
        if direction == "below-critical":
            title = f"Attendance critically low in {subject}"
            body = (
                f"Your attendance in {subject} dropped to {new_pct:.1f}% "
                f"(from {old_pct:.1f}%), below the critical {critical_threshold:.0f}% "
                f"level. Attendance below this level puts your exam eligibility at risk."
            )
            priority = HIGH_PRIORITY
        else:
            title = f"Attendance below target in {subject}"
            body = (
                f"Your attendance in {subject} dropped below the "
                f"{below_target_threshold:.0f}% target to {new_pct:.1f}% "
                f"(from {old_pct:.1f}%). Attend upcoming classes to recover."
            )
            priority = DEFAULT_PRIORITY
        notifications.append(
            {
                "student_id": crossing["student_id"],
                "faculty_id": None,
                "subject": subject,
                "message_type": "ATTENDANCE_WARNING",
                "title": title,
                "message_body": body,
                "priority": priority,
                "event_id": att_crossing_event_id(
                    crossing["student_id"],
                    crossing["subject_id"],
                    crossing["semester_no"],
                    direction,
                ),
            }
        )
    return notifications


def build_eligibility_warnings(
    flips: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Eligibility flips to 'Not Eligible' -> ELIGIBILITY_WARNING rows.

    Each flip: student_id, subject_id, subject_name, semester_no.
    At most one eligibility warning per student/semester (event identity is
    student + semester, so repeated flips do not re-notify).
    """
    notifications: List[Dict[str, Any]] = []
    for flip in flips:
        subject = flip["subject_name"]
        notifications.append(
            {
                "student_id": flip["student_id"],
                "faculty_id": None,
                "subject": subject,
                "message_type": "ELIGIBILITY_WARNING",
                "title": f"Exam eligibility at risk in {subject}",
                "message_body": (
                    f"Your attendance in {subject} is now below the eligibility "
                    f"requirement for semester {flip['semester_no']}. You are not "
                    f"currently eligible to appear for the examination."
                ),
                "priority": HIGH_PRIORITY,
                "event_id": eligibility_event_id(flip["student_id"], flip["semester_no"]),
            }
        )
    return notifications


def build_risk_alerts(risk_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Risk prediction rows -> RISK_ALERT notifications (inactive source).

    No verified writer currently produces risk predictions, so this builder is
    defined and tested but is NOT wired into any write path.
    Each row: student_id, subject_id (optional), risk_level, predicted_outcome,
    prediction_date, notes (optional).
    """
    notifications: List[Dict[str, Any]] = []
    for row in risk_rows:
        subject = row.get("subject_name") or row.get("subject_id")
        if subject:
            title = f"At-risk prediction for {subject}"
            body = (
                f"A deterministic risk prediction of '{row.get('predicted_outcome', '')}' "
                f"has been raised for {subject}."
            )
        else:
            title = "At-risk prediction raised"
            body = (
                f"A deterministic risk prediction of '{row.get('predicted_outcome', '')}' "
                f"has been raised for your profile."
            )
        notifications.append(
            {
                "student_id": row["student_id"],
                "faculty_id": None,
                "subject": subject,
                "message_type": "RISK_ALERT",
                "title": title,
                "message_body": body,
                "priority": HIGH_PRIORITY,
                "event_id": f"risk:{row['student_id']}:{row.get('prediction_date', '')}",
            }
        )
    return notifications


def build_timetable_changes(diffs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Timetable session diffs -> TIMETABLE_CHANGE notifications (inactive source).

    No timetable edit endpoint exists, so this builder is defined and tested
    but is NOT wired into any write path.
    Each diff: student_id, subject_id, subject_name, change ('added' |
    'moved' | 'removed'), detail (optional), academic_year (optional).
    """
    notifications: List[Dict[str, Any]] = []
    for diff in diffs:
        subject = diff["subject_name"]
        change = diff.get("change")
        if change == "added":
            title = f"Class added: {subject}"
            body = f"A new session for {subject} was added to your timetable."
        elif change == "removed":
            title = f"Class removed: {subject}"
            body = f"A session for {subject} was removed from your timetable."
        else:
            title = f"Class rescheduled: {subject}"
            body = f"A session for {subject} was moved to a new slot."
        notifications.append(
            {
                "student_id": diff["student_id"],
                "faculty_id": None,
                "subject": subject,
                "message_type": "TIMETABLE_CHANGE",
                "title": title,
                "message_body": body,
                "priority": DEFAULT_PRIORITY,
                "event_id": f"tt:{diff['student_id']}:{subject}:{change}",
            }
        )
    return notifications
