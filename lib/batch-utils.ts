import type { DashboardFilterOptions, AdminMlIntelligenceFilterOptions } from "./admin-api.ts"

/**
 * Canonical department codes matching PostgreSQL integer schema.
 * 1 = CSE (Computer Science and Engineering)
 * 2 = BBA (Bachelor of Business Administration)
 */
export const DEPARTMENT_CODES = {
  CSE: 1,
  BBA: 2,
} as const

export type DepartmentCode = typeof DEPARTMENT_CODES[keyof typeof DEPARTMENT_CODES]

/**
 * Normalize a batch or year value to a plain starting year string (e.g. "2023").
 * Handles formats: "2023", "23-24", "2023-24", "2023-2024".
 * Returns null for unrecognizable values.
 */
export function normalizeToYear(val: string): string | null {
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
 * Helper: normalize any batch/year strings to plain years and deduplicate
 */
export function normalizeList(items: string[]): string[] {
  const years = items
    .map(normalizeToYear)
    .filter((y): y is string => y !== null)
  return [...new Set(years)].sort()
}

/**
 * Resolves available starting batch years for the selected department.
 * Returns normalized plain year strings (e.g. "2023", "2024").
 *
 * - If no department is selected (All Departments): returns all institution starting years.
 * - If a specific department is selected: returns that department's starting years derived
 *   from real database records via filters.departments[].batches or filters.department_batches.
 */
export function getDepartmentBatches(
  departmentCode?: string | number | null,
  filters?: DashboardFilterOptions | AdminMlIntelligenceFilterOptions | null
): string[] {
  const deptStr = departmentCode != null && departmentCode !== "" ? departmentCode.toString() : ""

  if (!deptStr) {
    const source =
      filters?.batches && filters.batches.length > 0
        ? filters.batches
        : filters?.academic_years && filters.academic_years.length > 0
          ? filters.academic_years
          : []
    return normalizeList(source)
  }

  const selectedDept = (filters?.departments || []).find(
    (d) => d.department_code.toString() === deptStr
  )

  // 1. Department-specific batches attached to the department object (derived from DB admission_year)
  if (selectedDept?.batches && selectedDept.batches.length > 0) {
    return normalizeList(selectedDept.batches)
  }

  // 2. Department batches dictionary keyed by department code string
  if (filters?.department_batches?.[deptStr]?.length) {
    return normalizeList(filters.department_batches[deptStr])
  }

  const isBba =
    deptStr === String(DEPARTMENT_CODES.BBA) ||
    selectedDept?.department_short_name?.toUpperCase() === "BBA" ||
    selectedDept?.department_name?.toLowerCase().includes("business administration")

  const candidateBatches =
    filters?.batches && filters.batches.length > 0
      ? filters.batches
      : filters?.academic_years && filters.academic_years.length > 0
        ? filters.academic_years
        : []

  const normalized = normalizeList(candidateBatches)

  // Fallback for BBA when department_batches is not provided by caller:
  // In the real DB, BBA students only exist for batch 2023 onwards.
  if (isBba) {
    return normalized.filter((y) => Number(y) >= 2023)
  }

  return normalized
}
