import { test } from "node:test"
import assert from "node:assert/strict"

import type { ReportCardResponse } from "../student-api"
import { buildPrintReport, PENDING_MARK } from "./print-report-card.ts"

function subject(
  overrides: Partial<
    ReportCardResponse["semesters"][number]["subjects"][number]
  > = {}
) {
  return {
    subject_code: "SUB0001",
    subject_name: "Mathematics",
    semester: 1,
    credits: 4,
    internal_marks: 28.5,
    mid_sem_marks: 15,
    end_sem_marks: 42,
    total_marks: 85.5,
    percentage: 85.5,
    grade: "A",
    grade_point: 9,
    result_status: "PASS",
    attempt_number: 1,
    attendance_percentage: 92.5,
    ...overrides,
  }
}

function semester(
  overrides: Partial<ReportCardResponse["semesters"][number]> = {}
) {
  return {
    semester: 1,
    academic_year: "2025-2026",
    sgpa: 8.5,
    semester_percentage: 85.0,
    semester_grade: "A",
    semester_result: "pass",
    total_credits_earned: 24,
    credits_registered: 25,
    active_backlogs: 0,
    attendance_percentage: 91.0,
    subjects_registered: 2,
    academic_standing: "Good",
    subjects: [subject()],
    ...overrides,
  }
}

function response(
  overrides: Partial<ReportCardResponse> = {}
): ReportCardResponse {
  return {
    student_id: "STU000001",
    generated_at: "2026-08-11",
    profile: {
      student_id: "STU000001",
      first_name: "Jay",
      last_name: "Shah",
      department_name: "Computer Engineering",
      enrollment_no: 2023010001,
      admission_year: 2023,
      current_semester: 7,
      current_academic_year: "2025-2026",
      overall_cgpa: 7.9,
      overall_percentage: 79.5,
      latest_sgpa: 7.84,
      total_credits_earned: 168,
      total_credits_registered: 170,
      total_backlogs: 0,
      academic_standing: "Good",
    },
    semesters: [semester()],
    ...overrides,
  }
}

test("buildPrintReport maps header fields from profile", () => {
  const report = buildPrintReport(response())

  assert.equal(report.name, "Jay Shah")
  assert.equal(report.department, "Computer Engineering")
  assert.equal(report.enrollmentNo, "2023010001")
  assert.equal(report.admissionYear, "2023")
  assert.equal(report.currentSemester, "Semester 7")
  assert.equal(report.academicYear, "2025-2026")
  assert.equal(report.generatedAt, "2026-08-11")
  assert.equal(report.standing, "Good")
})

test("buildPrintReport maps summary fields", () => {
  const report = buildPrintReport(response())

  assert.deepEqual(report.summary, [
    { label: "Overall CGPA", value: "7.90" },
    { label: "Overall Percentage", value: "79.50%" },
    { label: "Latest SGPA", value: "7.84" },
    { label: "Credits Earned", value: "168 / 170" },
    { label: "Backlogs", value: "0" },
    { label: "Academic Standing", value: "Good" },
  ])
})

test("buildPrintReport represents every semester and every subject", () => {
  const data = response({
    semesters: [
      semester({
        semester: 1,
        subjects: [subject(), subject({ subject_code: "SUB0002" })],
      }),
      semester({
        semester: 2,
        subjects: [subject({ subject_code: "SUB0003" })],
      }),
    ],
  })

  const report = buildPrintReport(data)

  assert.equal(report.semesters.length, 2)
  assert.equal(report.semesters[0].semester, 1)
  assert.equal(report.semesters[0].rows.length, 2)
  assert.equal(report.semesters[1].semester, 2)
  assert.equal(report.semesters[1].rows.length, 1)
})

test("buildPrintReport maps subject row values", () => {
  const data = response({
    semesters: [semester({ subjects: [subject()] })],
  })

  const report = buildPrintReport(data)

  assert.deepEqual(report.semesters[0].rows[0], {
    subject: "Mathematics",
    code: "SUB0001",
    credits: "4",
    internal: "28.50",
    midSem: "15.00",
    endSem: "42.00",
    total: "85.50",
    percentage: "85.50%",
    grade: "A",
    result: "PASS",
    attendance: "92.5%",
  })
})

test("NULL subject values render as em-dash, never zero", () => {
  const data = response({
    semesters: [
      semester({
        subjects: [
          subject({
            internal_marks: null,
            mid_sem_marks: null,
            end_sem_marks: null,
            total_marks: null,
            percentage: null,
            grade: null,
            result_status: null,
            attendance_percentage: null,
            credits: null,
          }),
        ],
      }),
    ],
  })

  const row = buildPrintReport(data).semesters[0].rows[0]

  assert.equal(row.internal, PENDING_MARK)
  assert.equal(row.midSem, PENDING_MARK)
  assert.equal(row.endSem, PENDING_MARK)
  assert.equal(row.total, PENDING_MARK)
  assert.equal(row.percentage, PENDING_MARK)
  assert.equal(row.grade, PENDING_MARK)
  assert.equal(row.result, PENDING_MARK)
  assert.equal(row.attendance, PENDING_MARK)
  assert.equal(row.credits, PENDING_MARK)
})

test("NULL semester values render as em-dash, never zero", () => {
  const data = response({
    semesters: [
      semester({
        sgpa: null,
        semester_percentage: null,
        attendance_percentage: null,
        total_credits_earned: null,
        credits_registered: null,
        active_backlogs: null,
        semester_result: null,
      }),
    ],
  })

  const meta = buildPrintReport(data).semesters[0].meta

  assert.deepEqual(meta, [
    { label: "SGPA", value: PENDING_MARK },
    { label: "Percentage", value: PENDING_MARK },
    { label: "Attendance", value: PENDING_MARK },
    { label: "Credits", value: `${PENDING_MARK} / ${PENDING_MARK}` },
    { label: "Backlogs", value: PENDING_MARK },
    { label: "Result", value: PENDING_MARK },
  ])
})

test("pending result status is normalized to uppercase", () => {
  const data = response({
    semesters: [semester({ semester_result: "pending" })],
  })

  const result = buildPrintReport(data).semesters[0].meta.find(
    (item) => item.label === "Result"
  )

  assert.equal(result?.value, "PENDING")
})

test("buildPrintReport handles missing profile text as em-dash", () => {
  const data = response({
    profile: {
      ...response().profile,
      first_name: "",
      last_name: "",
      department_name: null,
      current_academic_year: null,
      academic_standing: null,
    },
  })

  const report = buildPrintReport(data)

  assert.equal(report.name, PENDING_MARK)
  assert.equal(report.department, PENDING_MARK)
  assert.equal(report.academicYear, PENDING_MARK)
  assert.equal(report.standing, PENDING_MARK)
})
