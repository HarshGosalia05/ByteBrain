import type { ReportCardResponse, ReportCardSemester } from "../student-api"

export type PrintField = {
  label: string
  value: string
}

export type PrintSubjectRow = {
  subject: string
  code: string
  credits: string
  internal: string
  midSem: string
  endSem: string
  total: string
  percentage: string
  grade: string
  result: string
  attendance: string
}

export type PrintSemester = {
  semester: number
  academicYear: string
  meta: PrintField[]
  rows: PrintSubjectRow[]
}

export type PrintReport = {
  name: string
  department: string
  enrollmentNo: string
  admissionYear: string
  currentSemester: string
  academicYear: string
  generatedAt: string
  standing: string
  summary: PrintField[]
  semesters: PrintSemester[]
}

export const PENDING_MARK = "—"

function formatNumber(
  value: number | null,
  decimals: number,
  suffix = ""
): string {
  return value === null ? PENDING_MARK : `${value.toFixed(decimals)}${suffix}`
}

function text(value: string | null): string {
  return value === null ? PENDING_MARK : value
}

function resultText(value: string | null): string {
  if (value === null) return PENDING_MARK
  const normalized = value.trim().toUpperCase()
  return normalized === "" ? PENDING_MARK : normalized
}

function creditsText(earned: number | null, registered: number | null): string {
  return `${formatNumber(earned, 0)} / ${formatNumber(registered, 0)}`
}

function buildSubjectRow(
  subject: ReportCardSemester["subjects"][number]
): PrintSubjectRow {
  return {
    subject: subject.subject_name,
    code: subject.subject_code,
    credits: formatNumber(subject.credits, 0),
    internal: formatNumber(subject.internal_marks, 2),
    midSem: formatNumber(subject.mid_sem_marks, 2),
    endSem: formatNumber(subject.end_sem_marks, 2),
    total: formatNumber(subject.total_marks, 2),
    percentage: formatNumber(subject.percentage, 2, "%"),
    grade: text(subject.grade),
    result: resultText(subject.result_status),
    attendance: formatNumber(subject.attendance_percentage, 1, "%"),
  }
}

function buildSemesterMeta(semester: ReportCardSemester): PrintField[] {
  return [
    { label: "SGPA", value: formatNumber(semester.sgpa, 2) },
    {
      label: "Percentage",
      value: formatNumber(semester.semester_percentage, 2, "%"),
    },
    {
      label: "Attendance",
      value: formatNumber(semester.attendance_percentage, 1, "%"),
    },
    {
      label: "Credits",
      value: creditsText(
        semester.total_credits_earned,
        semester.credits_registered
      ),
    },
    { label: "Backlogs", value: formatNumber(semester.active_backlogs, 0) },
    { label: "Result", value: resultText(semester.semester_result) },
  ]
}

export function buildPrintReport(data: ReportCardResponse): PrintReport {
  const { profile, semesters, generated_at } = data

  const summary: PrintField[] = [
    { label: "Overall CGPA", value: formatNumber(profile.overall_cgpa, 2) },
    {
      label: "Overall Percentage",
      value: formatNumber(profile.overall_percentage, 2, "%"),
    },
    { label: "Latest SGPA", value: formatNumber(profile.latest_sgpa, 2) },
    {
      label: "Credits Earned",
      value: creditsText(
        profile.total_credits_earned,
        profile.total_credits_registered
      ),
    },
    { label: "Backlogs", value: formatNumber(profile.total_backlogs, 0) },
    { label: "Academic Standing", value: text(profile.academic_standing) },
  ]

  const printSemesters: PrintSemester[] = semesters.map((semester) => ({
    semester: semester.semester,
    academicYear: semester.academic_year ?? "",
    meta: buildSemesterMeta(semester),
    rows: semester.subjects.map(buildSubjectRow),
  }))

  return {
    name: `${profile.first_name} ${profile.last_name}`.trim() || PENDING_MARK,
    department: text(profile.department_name),
    enrollmentNo: formatNumber(profile.enrollment_no, 0),
    admissionYear: formatNumber(profile.admission_year, 0),
    currentSemester:
      profile.current_semester === null
        ? PENDING_MARK
        : `Semester ${profile.current_semester}`,
    academicYear: text(profile.current_academic_year),
    generatedAt: text(generated_at),
    standing: text(profile.academic_standing),
    summary,
    semesters: printSemesters,
  }
}
