import type { DashboardFilterOptions, AdminMlIntelligenceFilterOptions } from "./admin-api.ts"

/**
 * Normalize a batch or year value to a plain starting year string (e.g. "2023").
 * Handles formats: "2023", "23-24", "2023-24", "2023-2024".
 * Returns null for unrecognizable values.
 */
function normalizeToYear(val: string): string | null {
  const cleaned = val.trim()
  // Plain 4-digit year
  if (/^\d{4}$/.test(cleaned)) return cleaned
  // 2-digit range: "23-24" -> "2023"
  const m2 = cleaned.match(/^(\d{2})-(\d{2})$/)
  if (m2) return `20${m2[1]}`
  // 4-digit start range: "2023-24" or "2023-2024" -> "2023"
  const m4 = cleaned.match(/^(\d{4})-(\d{2,4})$/)
  if (m4) return m4[1]
  return null
}

/**
 * Resolves available starting batch years for the selected department.
 * Returns normalized plain year strings (e.g. "2023", "2024").
 *
 * - If no department is selected (All Departments): returns all institution starting years.
 * - If a specific department is selected: returns that department's starting years.
 */
export function getDepartmentBatches(
  departmentCode?: string | number | null,
  filters?: DashboardFilterOptions | AdminMlIntelligenceFilterOptions | null
): string[] {
  const deptStr = departmentCode ? departmentCode.toString() : ""
  const selectedDept = (filters?.departments || []).find(
    (d) => d.department_code.toString() === deptStr
  )

  const isBba =
    deptStr === "2" ||
    selectedDept?.department_short_name?.toUpperCase() === "BBA" ||
    selectedDept?.department_name?.toLowerCase().includes("business administration")

  // Helper: normalize any batch/year strings to plain years and deduplicate
  const normalizeList = (items: string[]): string[] => {
    const years = items
      .map(normalizeToYear)
      .filter((y): y is string => y !== null)
    return [...new Set(years)].sort()
  }

  if (isBba) {
    // For BBA: zero-student starting years (2021, 2022)
    const zeroStudentYears = ["2021", "2022"]

    if (selectedDept?.batches && selectedDept.batches.length > 0) {
      const valid = normalizeList(selectedDept.batches).filter(
        (y) => !zeroStudentYears.includes(y)
      )
      if (valid.length > 0) return valid
    }

    if (deptStr && filters?.department_batches?.[deptStr]?.length) {
      const valid = normalizeList(filters.department_batches[deptStr]).filter(
        (y) => !zeroStudentYears.includes(y)
      )
      if (valid.length > 0) return valid
    }

    const candidateBatches =
      filters?.batches && filters.batches.length > 0
        ? filters.batches
        : filters?.academic_years && filters.academic_years.length > 0
          ? filters.academic_years
          : []

    const valid = normalizeList(candidateBatches).filter(
      (y) => !zeroStudentYears.includes(y)
    )
    return valid
  }

  // For CSE or All Departments: ALL starting years are returned
  if (selectedDept?.batches && selectedDept.batches.length > 0) {
    return normalizeList(selectedDept.batches)
  }

  if (deptStr && filters?.department_batches?.[deptStr]?.length) {
    return normalizeList(filters.department_batches[deptStr])
  }

  const source =
    filters?.batches && filters.batches.length > 0
      ? filters.batches
      : filters?.academic_years && filters.academic_years.length > 0
        ? filters.academic_years
        : []

  return normalizeList(source)
}
