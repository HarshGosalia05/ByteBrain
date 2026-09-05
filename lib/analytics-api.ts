import { getSessionUser, getSessionToken } from "./student-session.ts"

export type { SessionUser } from "./student-session.ts"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")
const BFF_TTL_MS = 60_000

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
      return { status, code: "unauthorized", message: "Your session is no longer valid. Please sign in again." }
    case 403:
      return { status, code: "unauthorized", message: "This account is not authorized." }
    case 404:
      return { status, code: "invalid", message: "The requested resource was not found." }
    case 422:
      return { status, code: "invalid", message: "The selected filter value is not valid." }
    case 503:
      return { status, code: "unavailable", message: "The analytics service is temporarily unavailable." }
    default:
      return { status, code: "server_error", message: "Something went wrong while loading analytics." }
  }
}

async function callAnalytics<T>(
  path: string,
  ttlMs: number,
  query?: Record<string, string | number | null | undefined>,
): Promise<BffResult<T>> {
  const user = await getSessionUser()
  if (!user) {
    return { ok: false, error: { status: 401, code: "unauthorized", message: "You must be signed in." } }
  }

  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined) params.set(key, String(value))
  }
  const qs = params.size > 0 ? `?${params.toString()}` : ""
  const fullPath = `/api/v1/analytics/${path}${qs}`
  const cacheKey = `${user.user_id}:${fullPath}`

  const hit = bffCache.get(cacheKey)
  if (hit && hit.expiresAt > Date.now()) return hit.value as BffResult<T>

  try {
    const token = (await getSessionToken()) ?? ""
    const res = await fetch(`${FASTAPI_URL}${fullPath}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    })
    if (!res.ok) return { ok: false, error: toBffError(res.status) }
    const data = (await res.json()) as T
    const result: BffResult<T> = { ok: true, data, fetchedAt: new Date().toISOString() }
    bffCache.set(cacheKey, { value: result, expiresAt: Date.now() + ttlMs })
    return result
  } catch {
    return { ok: false, error: { status: 503, code: "unavailable", message: "The analytics service is temporarily unavailable. Please try again later." } }
  }
}

// ---------------------------------------------------------------------------
// Types — match backend app.schemas.analytics exactly
// ---------------------------------------------------------------------------

export type StudentAcademicProfile = {
  student_id: string
  full_name: string | null
  department_code: number | null
  department_name: string | null
  current_semester: number | null
  current_academic_year: string | null
  overall_cgpa: number | null
  latest_sgpa: number | null
  total_backlogs: number
  overall_attendance_percentage: number | null
  total_subjects_enrolled: number
  total_credits_registered: number
}

export type SemesterTrendPoint = {
  semester_no: number
  academic_year: string | null
  semester_sgpa: number | null
  semester_percentage: number | null
  semester_attendance_percentage: number | null
  subjects_registered: number
  credits_registered: number
  credits_earned: number
  backlog_count: number
  semester_result: string | null
  academic_standing: string | null
}

export type StudentSemesterHistory = {
  student_id: string
  semesters: SemesterTrendPoint[]
}

export type StudentSubjectAttendance = {
  subject_id: string
  subject_code: string | null
  subject_name: string | null
  total_classes: number
  attended_classes: number
  attendance_percentage: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
}

export type StudentAttendanceSummary = {
  student_id: string
  semester_no: number | null
  overall_attendance_percentage: number | null
  total_classes: number
  attended_classes: number
  subjects: StudentSubjectAttendance[]
  at_risk_subjects: number
  ineligible_subjects: number
}

export type BacklogItem = {
  subject_id: string
  subject_code: string | null
  subject_name: string | null
  semester_no: number | null
  percentage: number | null
  grade: string | null
}

export type StudentBacklogSummary = {
  student_id: string
  total_backlogs: number
  backlogs: BacklogItem[]
}

export type GradeDistribution = { grade: string; count: number }

export type SubjectPerformanceSummary = {
  subject_id: string
  subject_code: string | null
  subject_name: string | null
  semester_no: number | null
  total_students: number
  average_percentage: number | null
  median_percentage: number | null
  min_percentage: number | null
  max_percentage: number | null
  pass_count: number
  fail_count: number
  pass_rate: number | null
  grade_distribution: GradeDistribution[]
}

export type SubjectAttendanceSummary = {
  subject_id: string
  subject_code: string | null
  subject_name: string | null
  semester_no: number | null
  total_students: number
  average_attendance_percentage: number | null
  eligible_count: number
  at_risk_count: number
  ineligible_count: number
  shortage_count: number
}

export type UnderperformerItem = {
  student_id: string
  full_name: string | null
  percentage: number | null
  grade: string | null
  attendance_percentage: number | null
}

export type SubjectUnderperformers = {
  subject_id: string
  semester_no: number | null
  threshold: number
  total_flagged?: number
  total?: number
  page?: number
  limit?: number
  total_pages?: number
  students: UnderperformerItem[]
}

export type DepartmentOverview = {
  department_code: number | null
  department_name: string | null
  semester_no: number | null
  academic_year: string | null
  total_students: number
  average_sgpa: number | null
  average_percentage: number | null
  average_attendance_percentage: number | null
  total_backlogs: number
  students_with_backlogs: number
}

export type PerformanceDistributionBucket = {
  label: string
  count: number
  percentage_of_total: number | null
}

export type SemesterPerformanceDistribution = {
  department_code: number | null
  semester_no: number | null
  academic_year: string | null
  total_students: number
  buckets: PerformanceDistributionBucket[]
}

export type AttendanceDistributionBucket = {
  band: string
  count: number
  percentage_of_total: number | null
}

export type AttendanceDistribution = {
  department_code: number | null
  semester_no: number | null
  total_students: number
  buckets: AttendanceDistributionBucket[]
}

export type BacklogDistributionBucket = {
  backlog_range: string
  count: number
  percentage_of_total: number | null
}

export type BacklogDistribution = {
  department_code: number | null
  total_students: number
  students_with_backlogs: number
  buckets: BacklogDistributionBucket[]
}

export type AtRiskStudent = {
  student_id: string
  full_name: string | null
  department_code: number | null
  current_semester: number | null
  overall_cgpa: number | null
  total_backlogs: number
  overall_attendance_percentage: number | null
  risk_reasons: string[]
  risk_score: number | null
}

export type AtRiskStudentsResult = {
  department_code: number | null
  semester_no: number | null
  total_flagged: number
  total?: number
  page?: number
  limit?: number
  total_pages?: number
  students: AtRiskStudent[]
}

export type BelowThresholdStudent = {
  student_id: string
  full_name: string | null
  subject_id: string
  subject_code: string | null
  attendance_percentage: number | null
  total_classes: number
  attended_classes: number
  classes_needed: number
}

export type BelowThresholdResult = {
  threshold: number
  semester_no: number | null
  total_flagged: number
  total?: number
  page?: number
  limit?: number
  total_pages?: number
  students: BelowThresholdStudent[]
}

export type SubjectNeedingAttention = {
  subject_id: string
  subject_code: string | null
  subject_name: string | null
  semester_no: number | null
  total_students: number
  average_percentage: number | null
  fail_rate: number | null
  average_attendance: number | null
  reasons: string[]
}

export type SubjectsNeedingAttentionResult = {
  department_code: number | null
  semester_no: number | null
  total_flagged: number
  total?: number
  page?: number
  limit?: number
  total_pages?: number
  subjects: SubjectNeedingAttention[]
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export type AnalyticsFilters = {
  department_code?: number | null
  semester_no?: number | null
  batch?: string | null
  academic_year?: string | null
  page?: number | null
  limit?: number | null
}

export function getStudentAcademicProfile(studentId: string): Promise<BffResult<StudentAcademicProfile>> {
  return callAnalytics<StudentAcademicProfile>(`students/${encodeURIComponent(studentId)}/academic-profile`, BFF_TTL_MS)
}

export function getStudentSemesterHistory(studentId: string, filters: AnalyticsFilters = {}): Promise<BffResult<StudentSemesterHistory>> {
  return callAnalytics<StudentSemesterHistory>(`students/${encodeURIComponent(studentId)}/semester-history`, BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getStudentAttendanceSummary(studentId: string, filters: AnalyticsFilters = {}): Promise<BffResult<StudentAttendanceSummary>> {
  return callAnalytics<StudentAttendanceSummary>(`students/${encodeURIComponent(studentId)}/attendance-summary`, BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getStudentBacklogSummary(studentId: string): Promise<BffResult<StudentBacklogSummary>> {
  return callAnalytics<StudentBacklogSummary>(`students/${encodeURIComponent(studentId)}/backlog-summary`, BFF_TTL_MS)
}

export function getSubjectPerformance(subjectId: string, filters: AnalyticsFilters = {}): Promise<BffResult<SubjectPerformanceSummary>> {
  return callAnalytics<SubjectPerformanceSummary>(`subjects/${encodeURIComponent(subjectId)}/performance`, BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getSubjectAttendance(subjectId: string, filters: AnalyticsFilters = {}): Promise<BffResult<SubjectAttendanceSummary>> {
  return callAnalytics<SubjectAttendanceSummary>(`subjects/${encodeURIComponent(subjectId)}/attendance`, BFF_TTL_MS, {
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getSubjectUnderperformers(subjectId: string, filters: AnalyticsFilters & { threshold?: number } = {}): Promise<BffResult<SubjectUnderperformers>> {
  const { threshold, ...rest } = filters
  return callAnalytics<SubjectUnderperformers>(`subjects/${encodeURIComponent(subjectId)}/underperformers`, BFF_TTL_MS, {
    semester_no: rest.semester_no,
    batch: rest.batch,
    academic_year: rest.academic_year,
    threshold,
    page: rest.page,
    limit: rest.limit,
  })
}

export function getDepartmentOverview(filters: AnalyticsFilters = {}): Promise<BffResult<DepartmentOverview>> {
  return callAnalytics<DepartmentOverview>("departments/overview", BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getPerformanceDistribution(filters: AnalyticsFilters = {}): Promise<BffResult<SemesterPerformanceDistribution>> {
  return callAnalytics<SemesterPerformanceDistribution>("departments/performance-distribution", BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getAttendanceDistribution(filters: AnalyticsFilters = {}): Promise<BffResult<AttendanceDistribution>> {
  return callAnalytics<AttendanceDistribution>("departments/attendance-distribution", BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getBacklogDistribution(filters: AnalyticsFilters = {}): Promise<BffResult<BacklogDistribution>> {
  return callAnalytics<BacklogDistribution>("departments/backlog-distribution", BFF_TTL_MS, {
    department_code: filters.department_code,
    batch: filters.batch,
    academic_year: filters.academic_year,
  })
}

export function getAtRiskStudents(filters: AnalyticsFilters = {}): Promise<BffResult<AtRiskStudentsResult>> {
  return callAnalytics<AtRiskStudentsResult>("at-risk/students", BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
    page: filters.page,
    limit: filters.limit,
  })
}

export function getBelowAttendanceThreshold(filters: AnalyticsFilters & { threshold?: number } = {}): Promise<BffResult<BelowThresholdResult>> {
  const { threshold, ...rest } = filters
  return callAnalytics<BelowThresholdResult>("at-risk/below-attendance-threshold", BFF_TTL_MS, {
    department_code: rest.department_code,
    semester_no: rest.semester_no,
    batch: rest.batch,
    academic_year: rest.academic_year,
    threshold,
    page: rest.page,
    limit: rest.limit,
  })
}

export function getSubjectsNeedingAttention(filters: AnalyticsFilters = {}): Promise<BffResult<SubjectsNeedingAttentionResult>> {
  return callAnalytics<SubjectsNeedingAttentionResult>("at-risk/subjects-needing-attention", BFF_TTL_MS, {
    department_code: filters.department_code,
    semester_no: filters.semester_no,
    batch: filters.batch,
    academic_year: filters.academic_year,
    page: filters.page,
    limit: filters.limit,
  })
}
