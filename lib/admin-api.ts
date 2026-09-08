import { getSessionUser, getSessionToken } from "./student-session.ts"
import type { M1V2PredictionData } from "./m1v2-prediction"
import type { M1V3PredictionData } from "./m1v3-prediction"
import type { M2TPPredictionData } from "./m2tp-prediction"
import type { M3V2PredictionData } from "./m3v2-prediction"

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
  total_semesters?: number | null
  semesters?: number[]
  batches?: string[]
}

export type DashboardFilterOptions = {
  batches?: string[]
  academic_years: string[]
  departments: DepartmentOption[]
  department_batches?: Record<string, string[]>
  semesters: number[]
  preferred_domains?: string[]
  dream_roles?: string[]
}

export { getDepartmentBatches } from "./batch-utils.ts"

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
  batch?: string | null
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
    const token = (await getSessionToken()) ?? ""
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

export function clearAdminBffCache(): void {
  bffCache.clear()
}

export function getAdminDashboard(
  filters: AdminDashboardFilters = {},
): Promise<BffResult<AdminDashboardData>> {
  return callFastapi<AdminDashboardData>("dashboard", BFF_TTL_MS, {
    query: {
      department_code: filters.department_code,
      batch: filters.batch ?? filters.academic_year,
      academic_year: filters.academic_year ?? filters.batch,
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
      batch: filters.batch ?? filters.academic_year,
      academic_year: filters.academic_year ?? filters.batch,
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
      batch: filters.batch ?? filters.academic_year,
      academic_year: filters.academic_year ?? filters.batch,
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
      batch: filters.batch ?? filters.academic_year,
      academic_year: filters.academic_year ?? filters.batch,
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
      batch: filters.batch ?? filters.academic_year,
      academic_year: filters.academic_year ?? filters.batch,
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
      batch: filters.batch ?? filters.academic_year,
      academic_year: filters.academic_year ?? filters.batch,
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
      batch: query.filters?.batch ?? query.filters?.academic_year,
      academic_year: query.filters?.academic_year ?? query.filters?.batch,
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

export type AdminStudentProfileData = {
  student: {
    student_id: string
    first_name: string
    last_name: string
    enrollment_no: number
    admission_year: number
    current_semester: number
    department_name: string | null
    current_academic_year: string | null
  }
  academic: {
    latest_sgpa: number | null
    overall_cgpa: number | null
    overall_percentage: number | null
    total_credits_registered: number | null
    total_credits_earned: number | null
    total_backlogs: number | null
    academic_standing: string | null
  }
  semesters: Array<{
    semester: number
    sgpa: number | null
    semester_percentage: number | null
    total_credits_earned: number | null
    attendance_percentage: number | null
    active_backlogs: number | null
    academic_year: string | null
  }>
  performance: Array<{
    semester: number
    subject_code: string
    subject_name: string
    total_marks: number | null
    percentage: number | null
    grade: string | null
    attendance_percentage: number | null
  }>
  risk: {
    risk_level: string | null
    risk_probability: number | null
    model_version: string | null
    generated_at: string | null
  } | null
  career: {
    score: number | null
    strengths: string[]
    areas_to_improve: string[]
  } | null
  generated_at: string
}

export function getAdminStudentProfile(
  studentId: string,
): Promise<BffResult<AdminStudentProfileData>> {
  return callFastapi<AdminStudentProfileData>(
    `students/${encodeURIComponent(studentId)}`,
    BFF_TTL_MS,
  )
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

export type AdminFacultyDetail = {
  faculty_id: string
  faculty_code: string | null
  full_name: string
  gender: string | null
  department_code: number
  department_name: string
  designation: string | null
  qualification: string | null
  specialization: string | null
  experience_years: number | null
  email: string | null
  phone_number: string | number | null
  joining_date: string | null
  employment_type: string | null
  status: string | null
}

export type AdminFacultyTeachingOverview = {
  total_subjects: number
  total_semesters: number
  active_students: number
  total_students_handled: number
  workload_hours: number | null
  assigned_departments: string[]
  assigned_semesters: number[]
}

export type AdminFacultySubjectItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  department_name: string
  semester_no: number | null
  academic_year: string | null
  student_count: number
  total_classes: number | null
  avg_attendance: number | null
  avg_marks_pct: number | null
  at_risk_count: number
}

export type AdminFacultyAcademicInsights = {
  overall_avg_marks: number | null
  overall_avg_attendance: number | null
  total_at_risk_count: number
  total_evaluated_records: number
  grade_distribution: Array<{ grade: string; count: number }>
}

export type AdminFacultyProfileData = {
  faculty: AdminFacultyDetail
  teaching_overview: AdminFacultyTeachingOverview
  subjects: AdminFacultySubjectItem[]
  insights: AdminFacultyAcademicInsights
  generated_at: string
}

export function getAdminFacultyProfile(
  facultyId: string,
): Promise<BffResult<AdminFacultyProfileData>> {
  return callFastapi<AdminFacultyProfileData>(
    `faculty/${encodeURIComponent(facultyId)}`,
    BFF_TTL_MS,
  )
}

// ---------------------------------------------------------------------------
// MD-07 â€” Admin Notifications, Announcements & Executive Insights
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

// ---------------------------------------------------------------------------
// ML-11 â€” Admin ML Intelligence
// ---------------------------------------------------------------------------

export type MlOverviewKpis = {
  total_students: number
  students_with_predictions: number
  coverage_percentage: number | null
  total_predictions: number
  models_status: Record<string, string>
}

export type FutureRiskDepartmentItem = {
  department_code: number
  department_name: string
  future_risk_count: number
  total_students: number
  risk_percentage: number | null
}

export type FutureRiskSemesterItem = {
  semester_no: number
  future_risk_count: number
  total_students: number
  risk_percentage: number | null
}

export type FutureRiskIntelligence = {
  future_at_risk_count: number
  future_at_risk_percentage: number | null
  future_low_risk_count: number
  current_deterministic_high_critical_count: number
  future_risk_by_department: FutureRiskDepartmentItem[]
  future_risk_by_semester: FutureRiskSemesterItem[]
  disclaimer: string
}

export type SubjectPerformanceItem = {
  subject_code: string
  subject_name: string
  department_name: string
  predicted_avg_mark: number
  students_count: number
}

export type DepartmentSubjectPerformanceItem = {
  department_code: number
  department_name: string
  predicted_avg_mark: number | null
}

export type M1SubjectIntelligence = {
  total_subject_predictions: number
  predicted_avg_subject_mark: number | null
  department_subject_performance: DepartmentSubjectPerformanceItem[]
  subjects_needing_attention: SubjectPerformanceItem[]
}

export type TheoryDistributionItem = {
  band: string
  count: number
}

export type PracticalDistributionItem = {
  band: string
  count: number
}

export type DepartmentNextSemPerformanceItem = {
  department_code: number
  department_name: string
  predicted_avg_theory_pct: number | null
  predicted_avg_practical_pct: number | null
}

export type M2NextSemPerformanceIntelligence = {
  predicted_avg_theory_pct: number | null
  predicted_avg_practical_pct: number | null
  theory_distribution: TheoryDistributionItem[]
  practical_distribution: PracticalDistributionItem[]
  department_performance_distribution: DepartmentNextSemPerformanceItem[]
  disclaimer: string
}

export type AcademicPredictionIntelligence = {
  m1: M1SubjectIntelligence
  m2: M2NextSemPerformanceIntelligence
}

export type DepartmentReadinessItem = {
  department_code: number
  department_name: string
  avg_score: number | null
  high_count: number
  medium_count: number
  low_count: number
}

export type FactorFrequencyItem = {
  factor: string
  frequency: number
}

export type CareerReadinessIntelligence = {
  avg_career_readiness_score: number | null
  readiness_level_counts: Record<string, number>
  department_readiness_distribution: DepartmentReadinessItem[]
  top_positive_factors: FactorFrequencyItem[]
  top_risk_factors: FactorFrequencyItem[]
  disclaimer: string
}

export type GroundedExecutiveInsight = {
  category: string
  title: string
  detail: string
  priority: "high" | "medium" | "low" | string
}

export type FilterDepartmentOption = {
  department_code: number
  department_name: string
  student_count: number
  department_short_name?: string | null
  batches?: string[]
}

export type FilterSemesterOption = {
  semester_no: number
  student_count: number
}

export type AdminMlIntelligenceFilterOptions = {
  departments: FilterDepartmentOption[]
  semesters: FilterSemesterOption[]
  batches?: string[]
  academic_years?: string[]
  department_batches?: Record<string, string[]>
}

export type AdminMlIntelligenceData = {
  overview: MlOverviewKpis
  future_risk: FutureRiskIntelligence
  academic_predictions: AcademicPredictionIntelligence
  career_readiness: CareerReadinessIntelligence
  executive_insights: GroundedExecutiveInsight[]
  filter_options: AdminMlIntelligenceFilterOptions
  generated_at: string
}

export function getAdminMLIntelligence(
  filters?: AdminDashboardFilters
): Promise<BffResult<AdminMlIntelligenceData>> {
  return callFastapi<AdminMlIntelligenceData>("ml-intelligence", BFF_TTL_MS, {
    query: filters as Record<string, string | number | null | undefined>,
  })
}

// M1-M4 batch generation (MD-08 / ML-11). POST queues an async backend
// job; the status endpoint is polled until the job settles.

export type MlGenerationModelStatus = {
  model: string
  eligible: number
  total: number
  completed: number
  failed: number
  skipped: number
}

export type MlGenerationJobStatus = {
  job_id: string
  status: "queued" | "running" | "completed" | "failed" | string
  models: string[]
  force: boolean
  department_code?: number | null
  semester?: number | null
  academic_year?: string | null
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  skipped_tasks: number
  progress_percent: number | null
  per_model: MlGenerationModelStatus[]
  errors: Array<{ student_id: string; model: string; error: string }>
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
}

export type GenerateMlPredictionsResponse = {
  job_id: string
  status: string
  models: string[]
  total_students: number
  message: string
}

export function startMLGeneration(
  filters?: AdminDashboardFilters,
  models?: string[],
  force?: boolean,
): Promise<BffResult<GenerateMlPredictionsResponse>> {
  return callFastapi<GenerateMlPredictionsResponse>(
    "ml-intelligence/generate",
    0,
    {
      method: "POST",
      query: filters as Record<string, string | number | null | undefined>,
      body: {
        models: models && models.length > 0 ? models : ["m1", "m2", "m3", "m4"],
        force: force ?? false,
      },
    },
  )
}

export function getMLGenerationStatus(
  jobId: string,
): Promise<BffResult<MlGenerationJobStatus>> {
  return callFastapi<MlGenerationJobStatus>(
    `ml-intelligence/generate/status/${encodeURIComponent(jobId)}`,
    0,
  )
}

// M1 V2 â€” Subject Marks Prediction (validated production model).
//
// The per-student endpoint lives at the generic /predict/m1v2/{student_id}
// route (not under /admin/), so we build the URL directly while reusing the
// Admin role guard + BFF cache. Server-side authorize_prediction_access allows
// Admin to read any student's M1 V2 prediction.
//
// NOTE (production limitation, user-confirmed): the backend exposes M1 V2
// predictions per-student only. There is NO M1 V2 cohort/aggregate endpoint,
// and M1 V2 is not wired into persisted ml_predictions. Consequently the Admin
// ML Intelligence page documents M1 V2 cohort analytics as "not yet available"
// rather than fabricating aggregate statistics. This typed client exists to
// keep the API surface complete for a future per-student drill-down, but the
// Admin UI does not render fabricated cohort numbers.

async function callAdminPredictM1V2<T>(
  studentId: string,
  ttlMs: number,
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

  const path = `predict/m1v2/${encodeURIComponent(studentId)}`
  const key = `${user.user_id}:${path}`
  const hit = bffCache.get(key)
  if (hit && hit.expiresAt > Date.now()) {
    return Promise.resolve(hit.value as BffResult<T>)
  }

  try {
    const token = (await getSessionToken()) ?? ""
    const res = await fetch(`${FASTAPI_URL}/api/v1/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
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

export function getAdminStudentM1V2(
  studentId: string
): Promise<BffResult<M1V2PredictionData>> {
  return callAdminPredictM1V2<M1V2PredictionData>(studentId, BFF_TTL_MS)
}

// Clean M1 V3 — Subject Marks Prediction (HistGradientBoostingRegressor, 38-feature contract).
// Per-student route at /predict/m1v3/{student_id}. Reuses Admin role guard + BFF cache.

async function callAdminPredictM1V3<T>(
  studentId: string,
  ttlMs: number,
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

  const path = `predict/m1v3/${encodeURIComponent(studentId)}`
  const key = `${user.user_id}:${path}`
  const hit = bffCache.get(key)
  if (hit && hit.expiresAt > Date.now()) {
    return Promise.resolve(hit.value as BffResult<T>)
  }

  try {
    const token = (await getSessionToken()) ?? ""
    const res = await fetch(`${FASTAPI_URL}/api/v1/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
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

export function getAdminStudentM1V3(
  studentId: string,
): Promise<BffResult<M1V3PredictionData>> {
  return callAdminPredictM1V3<M1V3PredictionData>(studentId, BFF_TTL_MS)
}

// M2-TP â€” Next-Semester Theory & Practical Performance Prediction (validated
// M2-TP package). Per-student route at /predict/m2tp/{student_id} (not under
// /admin/). Reuses the Admin role guard + BFF cache. Server-side
// authorize_prediction_access allows Admin to read any student's M2-TP forecast.

async function callAdminPredictM2TP<T>(
  studentId: string,
  ttlMs: number,
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

  const path = `predict/m2tp/${encodeURIComponent(studentId)}`
  const key = `${user.user_id}:${path}`
  const hit = bffCache.get(key)
  if (hit && hit.expiresAt > Date.now()) {
    return Promise.resolve(hit.value as BffResult<T>)
  }

  try {
    const token = (await getSessionToken()) ?? ""
    const res = await fetch(`${FASTAPI_URL}/api/v1/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
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

export function getAdminStudentM2TP(
  studentId: string
): Promise<BffResult<M2TPPredictionData>> {
  return callAdminPredictM2TP<M2TPPredictionData>(studentId, BFF_TTL_MS)
}

// M3 V2 â€” At-Risk Student Prediction (validated production model).
// Also a per-student route at /predict/m3v2/{student_id} (not under /admin/).
// Reuses the Admin role guard + BFF cache. Server-side authorize_prediction_access
// allows Admin to read any student's M3 V2 at-risk estimate.
// probability_at_risk is a model ESTIMATE, never a guarantee.

export function getAdminStudentM3V2(
  studentId: string
): Promise<BffResult<M3V2PredictionData>> {
  return callAdminPredictM3V2<M3V2PredictionData>(studentId, BFF_TTL_MS)
}

async function callAdminPredictM3V2<T>(
  studentId: string,
  ttlMs: number,
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

  const path = `predict/m3v2/${encodeURIComponent(studentId)}`
  const key = `${user.user_id}:${path}`
  const hit = bffCache.get(key)
  if (hit && hit.expiresAt > Date.now()) {
    return Promise.resolve(hit.value as BffResult<T>)
  }

  try {
    const token = (await getSessionToken()) ?? ""
    const res = await fetch(`${FASTAPI_URL}/api/v1/${path}`, {
      headers: { Authorization: `Bearer ${token}` },
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

// =============================================================================
// ML-12 Â§12.5 Admin health indicator â€” Faculty Feedback Loop
// =============================================================================

export type AdminFeedbackActionItem = {
  action: string
  count: number
}

export type AdminFeedbackDepartmentItem = {
  department_code: number
  department_name: string
  reviewed: number
  confirmed: number
  dismissed: number
}

export type AdminFeedbackSemesterItem = {
  semester_no: number | null
  reviewed: number
  confirmed: number
  dismissed: number
}

export type AdminMlFeedbackHealth = {
  total: number
  confirmed: number
  dismissed: number
  pending: number
  by_action: AdminFeedbackActionItem[]
  by_department: AdminFeedbackDepartmentItem[]
  by_semester: AdminFeedbackSemesterItem[]
  disclaimer: string
}

export function getAdminMlFeedbackHealth(): Promise<BffResult<AdminMlFeedbackHealth>> {
  return callFastapi<AdminMlFeedbackHealth>("ml-feedback", BFF_TTL_MS)
}

