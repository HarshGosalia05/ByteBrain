import { getSessionUser } from "./student-session.ts"

export type { SessionUser } from "./student-session.ts"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")
const BFF_TTL_MS = 60_000

export type DashboardKpis = {
  total_students: number
  total_faculty: number
  total_departments: number
  avg_sgpa: number | null
  avg_cgpa: number | null
  avg_percentage: number | null
  avg_attendance: number | null
  total_backlogs: number
  at_risk_students: number
}

export type DepartmentOption = {
  department_code: number
  department_name: string | null
  department_short_name: string | null
}

export type DashboardFilterOptions = {
  academic_years: string[]
  departments: DepartmentOption[]
  semesters: number[]
}

export type DepartmentPerformanceItem = {
  department_code: number
  department_name: string
  percentage: number | null
  sgpa: number | null
}

export type RiskDistributionItem = {
  risk_level: string
  count: number
}

export type AcademicTrendPoint = {
  semester: number
  avg_sgpa: number | null
  avg_percentage: number | null
  avg_attendance?: number | null
}

export type AttendanceDistributionItem = {
  status: string
  count: number
}

export type ResultOverviewItem = {
  status: string
  count: number
}

export type QuickInsight = {
  title: string
  detail: string
  kind: string
}

export type AdminDashboardData = {
  kpis: DashboardKpis
  filters: DashboardFilterOptions
  department_performance: DepartmentPerformanceItem[]
  risk_distribution: RiskDistributionItem[]
  academic_trend: AcademicTrendPoint[]
  attendance_distribution: AttendanceDistributionItem[]
  result_overview: ResultOverviewItem[]
  insights: QuickInsight[]
  generated_at: string
}

export type AdminDashboardFilters = {
  department_code?: number | null
  academic_year?: string | null
  semester?: number | null
}

export type BffError = {
  status: number
  code: "unauthorized" | "invalid" | "unavailable" | "server_error"
  message: string
}

export type BffResult<T> =
  | { ok: true; data: T; fetchedAt: string }
  | { ok: false; error: BffError }

type CacheEntry = { value: unknown; expiresAt: number }

const bffCache = new Map<string, CacheEntry>()

function toBffError(status: number): BffError {
  switch (status) {
    case 401:
      return {
        status,
        code: "unauthorized",
        message: "Your session is no longer valid. Please sign in again.",
      }
    case 403:
      return {
        status,
        code: "unauthorized",
        message: "This account is not allowed to view admin analytics.",
      }
    case 422:
      return {
        status,
        code: "invalid",
        message: "The selected filter value is not valid.",
      }
    case 503:
      return {
        status,
        code: "unavailable",
        message: "The academic service is temporarily unavailable.",
      }
    default:
      return {
        status,
        code: "server_error",
        message: "Something went wrong while loading institution analytics.",
      }
  }
}

async function callFastapi<T>(
  path: string,
  ttlMs: number,
  options?: {
    query?: Record<string, string | number | null | undefined>
  },
): Promise<BffResult<T>> {
  const user = await getSessionUser()
  if (!user) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to view this.",
      },
    }
  }
  if (user.role !== "Admin") {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to view admin analytics.",
      },
    }
  }

  const query = options?.query ?? {}
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) {
      params.set(key, String(value))
    }
  }
  const queryString = params.size > 0 ? `?${params.toString()}` : ""
  const pathWithQuery = `${path}${queryString}`
  const key = `${user.user_id}:${pathWithQuery}`

  const hit = bffCache.get(key)
  if (hit && hit.expiresAt > Date.now()) {
    return Promise.resolve(hit.value as BffResult<T>)
  }

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/admin/${pathWithQuery}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
    if (!res.ok) {
      return { ok: false, error: toBffError(res.status) }
    }
    const data = (await res.json()) as T
    const result: BffResult<T> = {
      ok: true,
      data,
      fetchedAt: new Date().toISOString(),
    }
    bffCache.set(key, { value: result, expiresAt: Date.now() + ttlMs })
    return result
  } catch {
    return {
      ok: false,
      error: {
        status: 503,
        code: "unavailable",
        message: "The academic service is temporarily unavailable. Please try again later.",
      },
    }
  }
}

export function getAdminDashboard(
  filters: AdminDashboardFilters = {},
): Promise<BffResult<AdminDashboardData>> {
  return callFastapi<AdminDashboardData>("dashboard", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      academic_year: filters.academic_year,
      semester: filters.semester,
    },
  })
}

// --- MD-03 Academic / Department / Subject intelligence -----------------------

export type AcademicOverviewKpis = {
  avg_sgpa: number | null
  avg_percentage: number | null
  pass_rate: number | null
  avg_attendance: number | null
  total_backlogs: number
  credits_earned: number
}

export type PassRatePoint = {
  semester: number
  pass_rate: number | null
}

export type GradeDistributionItem = {
  grade: string
  count: number
}

export type AcademicOverviewData = {
  kpis: AcademicOverviewKpis
  filters: DashboardFilterOptions
  trend: AcademicTrendPoint[]
  pass_rate_trend: PassRatePoint[]
  grade_distribution: GradeDistributionItem[]
  generated_at: string
}

export type DepartmentRiskItem = {
  risk_level: string
  count: number
}

export type DepartmentAnalyticsItem = {
  department_code: number
  department_name: string
  department_short_name: string | null
  total_students: number
  total_faculty: number
  avg_sgpa: number | null
  avg_percentage: number | null
  avg_attendance: number | null
  total_backlogs: number
  pass_rate: number | null
  at_risk_students: number
  risk_distribution: DepartmentRiskItem[]
}

export type DepartmentRankingItem = {
  rank: number
  department_code: number
  department_name: string
  total_students: number
  avg_sgpa: number | null
  avg_percentage: number | null
  avg_attendance: number | null
  at_risk_students: number
}

export type DepartmentAnalyticsData = {
  departments: DepartmentAnalyticsItem[]
  ranking: DepartmentRankingItem[]
  filters: DashboardFilterOptions
  generated_at: string
}

export type SubjectRow = {
  subject_code: string
  subject_name: string
  department_code: number
  department_name: string
  semester: number
  student_count: number
  avg_internal: number | null
  avg_mid_sem: number | null
  avg_end_sem: number | null
  avg_percentage: number | null
  pass_rate: number | null
  avg_attendance: number | null
}

export type AssessmentComponent = {
  component: string
  raw_average: number | null
  max_marks: number
  normalized_percentage: number | null
}

export type SubjectIntelligenceData = {
  subjects: SubjectRow[]
  top_subjects: SubjectRow[]
  weak_subjects: SubjectRow[]
  pass_rate_ranking: SubjectRow[]
  assessment_analysis: AssessmentComponent[]
  filters: DashboardFilterOptions
  generated_at: string
}

export function getAcademicOverview(
  filters: AdminDashboardFilters = {},
): Promise<BffResult<AcademicOverviewData>> {
  return callFastapi<AcademicOverviewData>("academic", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      academic_year: filters.academic_year,
      semester: filters.semester,
    },
  })
}

export function getDepartmentAnalytics(
  filters: AdminDashboardFilters = {},
): Promise<BffResult<DepartmentAnalyticsData>> {
  return callFastapi<DepartmentAnalyticsData>("academic/departments", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      academic_year: filters.academic_year,
      semester: filters.semester,
    },
  })
}

export function getSubjectIntelligence(
  filters: AdminDashboardFilters = {},
  search?: string | null,
): Promise<BffResult<SubjectIntelligenceData>> {
  return callFastapi<SubjectIntelligenceData>("academic/subjects", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      academic_year: filters.academic_year,
      semester: filters.semester,
      search: search || undefined,
    },
  })
}
