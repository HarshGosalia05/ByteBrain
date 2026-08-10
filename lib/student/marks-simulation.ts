// Shared marks-simulation utility (Student Module — Marks Simulator).
//
// Client-safe and deterministic. This is the UI mirror of the canonical
// derivation used by the backend (`derive_marks_fields` in
// `backend/app/services/faculty_service.py` + the `MARKS_*` band tables in
// `backend/app/core/config.py`). It is SIMULATION ONLY — it never reads from
// or writes to any database or API, and no academic data is persisted.
//
// Verified assessment model (MD-03 brief §4): Internal /20, Mid-Sem /50,
// End-Sem /70, Total /140. Percentage = total / 140 * 100. End-Sem must be
// >= 18/70 before a result may be treated as Pass.
//
// The library is HARD-validated: every function validates its inputs before
// deriving anything. No invalid value (negative, above maximum, NaN,
// Infinity, decimal, scientific notation) can reach the derivation.
//
// Keep the band tables below in lockstep with the backend so the simulator
// always matches the published result logic.

export const MARKS_TOTAL_MAX = 140
export const MARKS_PASS_PERCENTAGE = 40

export const MARKS_INTERNAL_MAX = 20
export const MARKS_MID_SEM_MAX = 50
export const MARKS_END_SEM_MAX = 70
export const MARKS_END_SEM_PASS_MIN = 18

export type MarksComponentKey = "internal_marks" | "mid_sem_marks" | "end_sem_marks"

type MarksComponentRange = {
  label: string
  min: number
  max: number
}

export const MARKS_COMPONENT_RANGE: Record<MarksComponentKey, MarksComponentRange> = {
  internal_marks: { label: "Internal", min: 0, max: MARKS_INTERNAL_MAX },
  mid_sem_marks: { label: "Mid-Sem", min: 0, max: MARKS_MID_SEM_MAX },
  end_sem_marks: { label: "End-Sem", min: 0, max: MARKS_END_SEM_MAX },
}

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

const REMARK_BANDS = [
  { minPercentage: 90, remark: "Excellent performance" },
  { minPercentage: 75, remark: "Good performance" },
  { minPercentage: 60, remark: "Satisfactory performance" },
  { minPercentage: 40, remark: "Needs improvement" },
] as const

const REMARK_LOW = "At risk - improvement required"

export type MarksFieldErrors = Record<MarksComponentKey, string | null>

export type MarksSimulationResult = {
  status: "incomplete" | "invalid" | "complete"
  complete: boolean
  errors: MarksFieldErrors
  end_sem_min_warning: boolean
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
  total_marks: number | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
  performance_category: string | null
  remarks: string | null
}

export type MarksSimulationInput = {
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
}

/**
 * Parse a single raw text value for one marks component.
 *
 * Rules:
 *   * empty / whitespace-only  -> incomplete (value null, no error)
 *   * whole-number digits only -> parsed integer ("" is not allowed once the
 *     input is non-empty: negatives, "+", ".", "e", spaces, NaN, Infinity and
 *     scientific notation never become a valid value)
 *   * anything else / out of range -> value null + a field-level error
 *
 * The returned `valid` flag tells the caller whether the raw text may be
 * stored as the field state.
 */
export function parseMarksField(
  raw: string,
  field: MarksComponentKey,
): { value: number | null; error: string | null; valid: boolean } {
  const range = MARKS_COMPONENT_RANGE[field]
  const trimmed = raw.trim()
  if (trimmed === "") {
    return { value: null, error: null, valid: true }
  }
  if (!/^\d+$/.test(trimmed)) {
    return {
      value: null,
      error: `${range.label} marks must be between ${range.min} and ${range.max}.`,
      valid: false,
    }
  }
  const parsed = Number(trimmed)
  if (!Number.isSafeInteger(parsed) || parsed < range.min || parsed > range.max) {
    return {
      value: null,
      error: `${range.label} marks must be between ${range.min} and ${range.max}.`,
      valid: false,
    }
  }
  return { value: parsed, error: null, valid: true }
}

function isSafeMarksValue(value: number, field: MarksComponentKey): boolean {
  const range = MARKS_COMPONENT_RANGE[field]
  return Number.isInteger(value) && value >= range.min && value <= range.max
}

/**
 * Pure, hard-validated simulation. Never calculates from invalid input.
 *
 *   * any required component missing   -> status "incomplete"
 *   * any component invalid (out of range / not an integer) -> status "invalid"
 *   * all three valid                 -> status "complete" with derived values
 *
 * Derived values (total/percentage/grade/result/category/remarks) are ONLY
 * ever produced for a fully valid simulation. End-Sem below the 18/70 pass
 * minimum is still a valid input, but the result can never be "Pass" and the
 * `end_sem_min_warning` flag is set.
 */
export function simulateMarks(input: MarksSimulationInput): MarksSimulationResult {
  const components: MarksComponentKey[] = [
    "internal_marks",
    "mid_sem_marks",
    "end_sem_marks",
  ]

  const errors: MarksFieldErrors = {
    internal_marks: null,
    mid_sem_marks: null,
    end_sem_marks: null,
  }

  let incomplete = false
  for (const key of components) {
    const raw = input[key]
    const value = raw === undefined ? null : raw
    if (value === null) {
      incomplete = true
      continue
    }
    if (!isSafeMarksValue(value, key)) {
      errors[key] = `${MARKS_COMPONENT_RANGE[key].label} marks must be between ${MARKS_COMPONENT_RANGE[key].min} and ${MARKS_COMPONENT_RANGE[key].max}.`
    }
  }

  const endSem = input.end_sem_marks === undefined ? null : input.end_sem_marks
  const endSemMinWarning =
    endSem !== null && Number.isInteger(endSem) && endSem >= 0 && endSem < MARKS_END_SEM_PASS_MIN

  const invalid =
    errors.internal_marks !== null || errors.mid_sem_marks !== null || errors.end_sem_marks !== null

  const base: MarksSimulationResult = {
    status: invalid ? "invalid" : incomplete ? "incomplete" : "complete",
    complete: false,
    errors,
    end_sem_min_warning: endSemMinWarning,
    internal_marks: input.internal_marks === undefined ? null : input.internal_marks,
    mid_sem_marks: input.mid_sem_marks === undefined ? null : input.mid_sem_marks,
    end_sem_marks: endSem,
    total_marks: null,
    percentage: null,
    grade: null,
    grade_point: null,
    result_status: null,
    performance_category: null,
    remarks: null,
  }

  if (invalid || incomplete) {
    return base
  }

  const internal = input.internal_marks as number
  const mid = input.mid_sem_marks as number
  const end = input.end_sem_marks as number

  const total = internal + mid + end
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

  let remark = REMARK_LOW
  for (const band of REMARK_BANDS) {
    if (percentage >= band.minPercentage) {
      remark = band.remark
      break
    }
  }

  return {
    ...base,
    status: "complete",
    complete: true,
    total_marks: total,
    percentage,
    grade,
    grade_point: gradePoint,
    result_status:
      percentage >= MARKS_PASS_PERCENTAGE && end >= MARKS_END_SEM_PASS_MIN ? "Pass" : "Fail",
    performance_category: category,
    remarks: remark,
  }
}
