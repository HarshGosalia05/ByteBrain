// Shared attendance-simulation utility (Student Module — Attendance Simulator).
//
// Client-safe and deterministic. This is the UI mirror of the canonical
// derivation used by the backend (`compute_attendance_what_if` in
// `backend/app/services/student_analytics_rules.py`, which reuses
// `attendance_aggregate_fields` in `backend/app/services/faculty_service.py`,
// and the `ATTENDANCE_*` / `FACULTY_ATTENDANCE_*` thresholds in
// `backend/app/core/config.py`). It is SIMULATION ONLY — it never reads from
// or writes to any database or API, and no attendance data is persisted.
//
// Projection model: the next `hypothetical_present` classes are attended and
// the next `hypothetical_absent` are missed:
//   new_total    = total + present + absent
//   new_attended = attended + present
//
// Keep the band tables below in lockstep with the backend so the simulator
// always matches the published attendance logic.

export const ATTENDANCE_TARGET_PERCENTAGE = 75
export const ATTENDANCE_CRITICAL_PERCENTAGE = 60
export const ATTENDANCE_GOOD_SPLIT = 80
export const ATTENDANCE_EXCELLENT_PERCENTAGE = 90

export type AttendanceSimulationResult = {
  total_classes: number
  attended_classes: number
  hypothetical_present: number
  hypothetical_absent: number
  current_attendance: number | null
  resulting_attendance: number | null
  delta: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
  target_attendance: number
  at_target: boolean
  classes_to_reach_target: number | null
  classes_to_skip_below_target: number | null
  complete: boolean
  message: string | null
}

function round2(value: number): number {
  return Math.round(value * 100) / 100
}

// Mirror of `attendance_aggregate_fields` in faculty_service.py.
function deriveAttendanceFields(
  percentage: number,
  compliance: number,
): Pick<
  AttendanceSimulationResult,
  "attendance_status" | "eligibility_status" | "shortage_flag"
> {
  let status: string
  if (percentage < ATTENDANCE_CRITICAL_PERCENTAGE) {
    status = "Critical"
  } else if (percentage < compliance) {
    status = "Low"
  } else if (percentage < ATTENDANCE_GOOD_SPLIT) {
    status = "Average"
  } else if (percentage < ATTENDANCE_EXCELLENT_PERCENTAGE) {
    status = "Good"
  } else {
    status = "Excellent"
  }
  return {
    attendance_status: status,
    eligibility_status: percentage >= compliance ? "Eligible" : "Not Eligible",
    shortage_flag: percentage < compliance ? "Yes" : "No",
  }
}

export function simulateAttendance(input: {
  total_classes: number | null
  attended_classes: number | null
  hypothetical_present?: number
  hypothetical_absent?: number
  target_attendance?: number
}): AttendanceSimulationResult {
  const {
    total_classes,
    attended_classes,
    hypothetical_present = 0,
    hypothetical_absent = 0,
  } = input
  const target = input.target_attendance ?? ATTENDANCE_TARGET_PERCENTAGE

  const incomplete: AttendanceSimulationResult = {
    total_classes: total_classes ?? 0,
    attended_classes: attended_classes ?? 0,
    hypothetical_present,
    hypothetical_absent,
    current_attendance: null,
    resulting_attendance: null,
    delta: null,
    attendance_status: null,
    eligibility_status: null,
    shortage_flag: null,
    target_attendance: target,
    at_target: false,
    classes_to_reach_target: null,
    classes_to_skip_below_target: null,
    complete: false,
    message: null,
  }

  // A missing baseline keeps every projected field null — never a partial
  // percentage, never a COALESCE(0) projection.
  if (
    total_classes === null ||
    attended_classes === null ||
    total_classes <= 0 ||
    attended_classes < 0 ||
    attended_classes > total_classes
  ) {
    return incomplete
  }

  const current = round2((attended_classes / total_classes) * 100)
  const newTotal = total_classes + hypothetical_present + hypothetical_absent
  const newAttended = attended_classes + hypothetical_present
  const resulting = newTotal > 0 ? round2((newAttended / newTotal) * 100) : current

  const fields = deriveAttendanceFields(resulting, target)

  const targetFraction = target / 100
  let classesToReachTarget: number
  if (current < target) {
    classesToReachTarget = Math.max(
      1,
      Math.ceil(
        (targetFraction * total_classes - attended_classes) / (1 - targetFraction),
      ),
    )
  } else {
    classesToReachTarget = 0
  }

  let classesToSkipBelowTarget: number
  if (current >= target) {
    classesToSkipBelowTarget = Math.max(
      0,
      Math.floor(attended_classes / targetFraction - total_classes),
    )
  } else {
    classesToSkipBelowTarget = 0
  }

  const atTarget = resulting >= target
  const message = atTarget
    ? `Attendance holds at ${resulting.toFixed(1)}% — at or above the ${target.toFixed(0)}% target.`
    : `Attendance drops to ${resulting.toFixed(1)}% — below the ${target.toFixed(0)}% target.`

  return {
    total_classes,
    attended_classes,
    hypothetical_present,
    hypothetical_absent,
    current_attendance: current,
    resulting_attendance: resulting,
    delta: round2(resulting - current),
    attendance_status: fields.attendance_status,
    eligibility_status: fields.eligibility_status,
    shortage_flag: fields.shortage_flag,
    target_attendance: target,
    at_target: atTarget,
    classes_to_reach_target: classesToReachTarget,
    classes_to_skip_below_target: classesToSkipBelowTarget,
    complete: true,
    message,
  }
}
