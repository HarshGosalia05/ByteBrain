// Shared marks-simulation utility (Student Module — Marks Simulator).
//
// Client-safe and deterministic. This is the UI mirror of the canonical
// derivation used by the backend (`derive_marks_fields` in
// `backend/app/services/faculty_service.py` + the `MARKS_*` band tables in
// `backend/app/core/config.py`). It is SIMULATION ONLY — it never reads from
// or writes to any database or API, and no academic data is persisted.
//
// Verified assessment model (MD-03 brief §4): Internal /20, Mid-Sem /50,
// End-Sem /70, Total /140. Percentage = total / 140 * 100.
//
// Keep the band tables below in lockstep with the backend so the simulator
// always matches the published result logic.

export const MARKS_TOTAL_MAX = 140
export const MARKS_PASS_PERCENTAGE = 40

const GRADE_BANDS = [
  { minPercentage: 90, grade: "O", gradePoint: 10 },
  { minPercentage: 80, grade: "A+", gradePoint: 9 },
  { minPercentage: 70, grade: "A", gradePoint: 8 },
  { minPercentage: 60, grade: "B+", gradePoint: 7 },
  { minPercentage: 50, grade: "B", gradePoint: 6 },
  { minPercentage: 40, grade: "C", gradePoint: 5 },
] as const

const GRADE_FAIL = { grade: "F", gradePoint: 0 }

const CATEGORY_BANDS = [
  { minPercentage: 90, category: "Top" },
  { minPercentage: 80, category: "Above Average" },
  { minPercentage: 60, category: "Average" },
  { minPercentage: 40, category: "Below Average" },
] as const

const CATEGORY_LOW = "Low Performer"

export type MarksSimulationResult = {
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
  complete: boolean
  total_marks: number | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
  performance_category: string | null
}

export function simulateMarks(input: {
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
}): MarksSimulationResult {
  const { internal_marks, mid_sem_marks, end_sem_marks } = input

  // A NULL component keeps every derived field NULL (end-sem not entered yet).
  if (
    internal_marks === null ||
    mid_sem_marks === null ||
    end_sem_marks === null
  ) {
    return {
      internal_marks,
      mid_sem_marks,
      end_sem_marks,
      complete: false,
      total_marks: null,
      percentage: null,
      grade: null,
      grade_point: null,
      result_status: null,
      performance_category: null,
    }
  }

  const total = internal_marks + mid_sem_marks + end_sem_marks
  const percentage = Math.round((total / MARKS_TOTAL_MAX) * 100 * 100) / 100

  let grade = GRADE_FAIL.grade
  let gradePoint = GRADE_FAIL.gradePoint
  for (const band of GRADE_BANDS) {
    if (percentage >= band.minPercentage) {
      grade = band.grade
      gradePoint = band.gradePoint
      break
    }
  }

  let category = CATEGORY_LOW
  for (const band of CATEGORY_BANDS) {
    if (percentage >= band.minPercentage) {
      category = band.category
      break
    }
  }

  return {
    internal_marks,
    mid_sem_marks,
    end_sem_marks,
    complete: true,
    total_marks: total,
    percentage,
    grade,
    grade_point: gradePoint,
    result_status:
      percentage >= MARKS_PASS_PERCENTAGE ? "Pass" : "Fail",
    performance_category: category,
  }
}
