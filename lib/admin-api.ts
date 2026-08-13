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
  preferred_domains?: string[]
  dream_roles?: string[]
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
  preferred_domain?: string | null
  dream_job_role?: string | null
  internship_status?: string | null
  placement_readiness_level?: string | null
  career_status?: string | null
  target_package?: string | null
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
    method?: string
    body?: unknown
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
    const method = options?.method ?? "GET"
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
    }
    if (options?.body) {
      headers["Content-Type"] = "application/json"
    }

    const res = await fetch(`${FASTAPI_URL}/api/v1/admin/${pathWithQuery}`, {
      method,
      headers,
      body: options?.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
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

// --- MD-04 Attendance & Risk Intelligence ------------------------------------

export type AttendanceKpis = {
  avg_attendance: number | null
  students_below_target: number
  critical_shortage_students: number
  eligible_students: number
  not_eligible_students: number
}

export type AttendanceByDepartmentItem = {
  department_code: number
  department_name: string
  avg_attendance: number | null
}

export type AttendanceBySemesterItem = {
  semester: number
  avg_attendance: number | null
}

export type SubjectAttendanceRow = {
  subject_code: string
  subject_name: string
  department_code: number
  department_name: string
  semester: number
  student_count: number
  avg_attendance: number | null
  below_target_count: number
  critical_shortage_count: number
  eligible_count: number
  not_eligible_count: number
}

export type ShortageStudentRow = {
  student_id: string
  student_name: string
  enrollment_no: number
  department_code: number
  department_name: string
  semester: number
  subject_code: string
  subject_name: string
  attendance_percentage: number | null
  required_target: number
  shortage: number | null
  eligibility_status: string | null
}

export type AttendanceIntelligenceData = {
  kpis: AttendanceKpis
  required_target: number
  filters: DashboardFilterOptions
  by_department: AttendanceByDepartmentItem[]
  by_semester: AttendanceBySemesterItem[]
  distribution: AttendanceDistributionItem[]
  subjects: SubjectAttendanceRow[]
  subjects_total: number
  shortage_total: number
  shortage_students: ShortageStudentRow[]
  limit: number
  offset: number
  generated_at: string
}

export type RiskKpis = {
  total_predicted: number
  low: number
  moderate: number
  high: number
  critical: number
  at_risk: number
}

export type RiskByDepartmentItem = {
  department_code: number
  department_name: string
  distribution: RiskDistributionItem[]
}

export type RiskBySemesterItem = {
  semester: number
  distribution: RiskDistributionItem[]
}

export type RiskStudentRow = {
  student_id: string
  student_name: string
  enrollment_no: number
  department_code: number
  department_name: string
  semester: number | null
  academic_year: string | null
  attendance: number | null
  percentage: number | null
  backlogs: number | null
  academic_standing: string | null
  risk: string
}

export type EarlyWarningRow = {
  student_id: string
  student_name: string
  enrollment_no: number
  department_code: number
  department_name: string
  semester: number | null
  severity: string
  primary_concern: string | null
  supporting_signals: string[]
  recommended_action: string | null
}

export type RiskIntelligenceData = {
  kpis: RiskKpis
  filters: DashboardFilterOptions
  distribution: RiskDistributionItem[]
  by_department: RiskByDepartmentItem[]
  by_semester: RiskBySemesterItem[]
  students: RiskStudentRow[]
  students_total: number
  early_warning: EarlyWarningRow[]
  limit: number
  offset: number
  generated_at: string
}

export function getAttendanceIntelligence(
  filters: AdminDashboardFilters = {},
  search?: string | null,
): Promise<BffResult<AttendanceIntelligenceData>> {
  return callFastapi<AttendanceIntelligenceData>("attendance", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      academic_year: filters.academic_year,
      semester: filters.semester,
      search: search || undefined,
    },
  })
}

export function getRiskIntelligence(
  filters: AdminDashboardFilters = {},
  risk?: string | null,
  search?: string | null,
): Promise<BffResult<RiskIntelligenceData>> {
  return callFastapi<RiskIntelligenceData>("risk", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      academic_year: filters.academic_year,
      semester: filters.semester,
      risk: risk || undefined,
      search: search || undefined,
    },
  })
}

// --- MD-05 Admin Student & Faculty Overview ----------------------------------

export type AdminStudentRow = {
  student_id: string
  student_name: string
  enrollment_no: number
  email: string | null
  department_code: number
  department_name: string
  semester: number | null
  academic_year: string | null
  sgpa: number | null
  cgpa: number | null
  percentage: number | null
  attendance: number | null
  backlogs: number | null
  risk: string | null
  academic_standing: string | null
  preferred_domain?: string | null
  dream_job_role?: string | null
  preferred_industry?: string | null
  preferred_work_mode?: string | null
  target_package_lpa?: number | null
  higher_studies_interest?: string | null
  entrepreneurship_interest?: string | null
  certification_interest?: string | null
  internship_completed?: string | null
  placement_readiness_level?: string | null
  average_sleep_hours?: number | null
  daily_study_hours?: number | null
  screen_time_hours?: number | null
  physical_activity?: string | null
  stress_level?: string | null
  mental_wellbeing?: string | null
  attendance_commitment?: string | null
  part_time_job?: string | null
  internet_access?: string | null
  preferred_learning_mode?: string | null
}

export type AdminStudentsData = {
  filters: DashboardFilterOptions
  students: AdminStudentRow[]
  students_total: number
  limit: number
  offset: number
  sort_by: string
  sort_dir: string
  generated_at: string
}

export type AdminStudentsQuery = {
  filters?: AdminDashboardFilters
  risk?: string | null
  search?: string | null
  sortBy?: string
  sortDir?: string
  limit?: number
  offset?: number
}

export const ADMIN_STUDENT_SORT_FIELDS = [
  "name",
  "sgpa",
  "percentage",
  "attendance",
  "backlogs",
  "risk",
] as const

export type AdminStudentSortField = (typeof ADMIN_STUDENT_SORT_FIELDS)[number]

export function getAdminStudents(
  query: AdminStudentsQuery = {},
): Promise<BffResult<AdminStudentsData>> {
  return callFastapi<AdminStudentsData>("students", BFF_TTL_MS, {
    query: {
      department_code: query.filters?.department_code,
      academic_year: query.filters?.academic_year,
      semester: query.filters?.semester,
      preferred_domain: query.filters?.preferred_domain || undefined,
      dream_job_role: query.filters?.dream_job_role || undefined,
      internship_status: query.filters?.internship_status || undefined,
      placement_readiness_level: query.filters?.placement_readiness_level || undefined,
      career_status: query.filters?.career_status || undefined,
      target_package: query.filters?.target_package || undefined,
      risk: query.risk || undefined,
      search: query.search || undefined,
      sort_by: query.sortBy || undefined,
      sort_dir: query.sortDir || undefined,
      limit: query.limit,
      offset: query.offset,
    },
  })
}

export type AdminFacultyKpis = {
  total_faculty: number
  active_faculty: number
  department_count: number
}

export type AdminFacultyByDepartmentItem = {
  department_code: number
  department_name: string
  count: number
}

export type AdminFacultyByDesignationItem = {
  designation: string
  count: number
}

export type AdminFacultyRow = {
  faculty_id: string
  faculty_code: string | null
  full_name: string
  department_code: number
  department_name: string
  designation: string | null
  subject_count: number
  student_count: number
  workload_hours: number | null
}

export type AdminFacultyData = {
  kpis: AdminFacultyKpis
  by_department: AdminFacultyByDepartmentItem[]
  by_designation: AdminFacultyByDesignationItem[]
  faculty: AdminFacultyRow[]
  generated_at: string
}

export function getAdminFaculty(): Promise<BffResult<AdminFacultyData>> {
  return callFastapi<AdminFacultyData>("faculty", BFF_TTL_MS)
}

// ---------------------------------------------------------------------------
// MD-07 — Admin Notifications, Announcements & Executive Insights
// ---------------------------------------------------------------------------

export type CreateAnnouncementInput = {
  title: string
  message: string
  type: "ANNOUNCEMENT" | "ACADEMIC_NOTICE" | "HOLIDAY" | "EVENT" | "SYSTEM_NOTICE"
  target_audience: "students" | "faculty" | "both"
  department_code?: number | null
  priority?: "Normal" | "High" | "Urgent"
}

export type CreateAnnouncementResult = {
  announcement_id: string
  title: string
  type: string
  target_audience: string
  recipients_notified: number
  created_at: string
}

export type AdminAnnouncementItem = {
  title: string
  message: string
  type: string
  target_audience: string
  department_code: number | null
  priority: string
  recipient_count: number
  created_at: string
}

export type AdminAnnouncementsData = {
  announcements: AdminAnnouncementItem[]
  total_count: number
  generated_at: string
}

export type ExecutiveDepartmentPerformance = {
  department_code: number
  department_name: string
  student_count: number
  avg_cgpa: number | null
  avg_percentage: number | null
}

export type ExecutiveSubjectPerformance = {
  subject_code: string
  subject_name: string
  avg_percentage: number | null
  student_count: number
}

export type ExecutiveSummaryData = {
  strongest_department: ExecutiveDepartmentPerformance | null
  weakest_department: ExecutiveDepartmentPerformance | null
  weakest_subject: ExecutiveSubjectPerformance | null
  attendance_concern_department: string | null
  attendance_shortage_count: number
  total_at_risk_students: number
  high_risk_count: number
  critical_risk_count: number
  top_risk_department: string | null
  total_students: number
  overall_avg_cgpa: number | null
  overall_attendance_pct: number | null
  internship_completion_rate: number | null
  insights: string[]
  generated_at: string
}

export function createAnnouncement(
  input: CreateAnnouncementInput,
): Promise<BffResult<CreateAnnouncementResult>> {
  return callFastapi<CreateAnnouncementResult>("announcements", 0, {
    method: "POST",
    body: input,
  })
}

export function getAdminAnnouncements(): Promise<BffResult<AdminAnnouncementsData>> {
  return callFastapi<AdminAnnouncementsData>("announcements", BFF_TTL_MS)
}

export function getExecutiveSummary(): Promise<BffResult<ExecutiveSummaryData>> {
  return callFastapi<ExecutiveSummaryData>("executive-summary", BFF_TTL_MS)
}

