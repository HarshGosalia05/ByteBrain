import { cookies } from "next/headers"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")
const BFF_TTL_MS = 60_000

export type SessionUser = {
  user_id: string
  username: string
  role: string
  department?: string | null
  student_id?: string | null
  faculty_id?: string | null
}

export type StudentProfile = {
  student_id: string
  first_name: string
  last_name: string
  enrollment_no: number
  admission_year: number
  current_semester: number
  department_name: string | null
  current_academic_year: string | null
  latest_sgpa: number | null
  overall_cgpa: number | null
  overall_percentage: number | null
  total_credits_registered: number | null
  total_credits_earned: number | null
  total_backlogs: number | null
  academic_standing: string | null
}

export type AcademicOverview = {
  current_semester: number | null
  current_academic_year: string | null
  latest_sgpa: number | null
  overall_cgpa: number | null
  overall_percentage: number | null
  total_credits_registered: number | null
  total_credits_earned: number | null
  total_backlogs: number | null
  academic_standing: string | null
}

export type SemesterSummaryItem = {
  semester: number
  sgpa: number
  total_credits_earned: number
  attendance_percentage: number
  active_backlogs: number
  academic_year: string | null
  subjects_registered: number | null
  credits_registered: number | null
  semester_percentage: number | null
  semester_grade: string | null
  semester_result: string | null
  academic_standing: string | null
}

export type SemesterSummaryResponse = {
  student_id: string
  overview: AcademicOverview
  summaries: SemesterSummaryItem[]
}

export type SubjectPerformanceItem = {
  semester: number
  subject_id: string
  subject_code: string
  subject_name: string
  credits: number | null
  academic_year: string | null
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
  total_marks: number | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
  attempt_number: number | null
  performance_category: string | null
  remarks: string | null
  attendance_percentage: number | null
  updated_at: string | null
}

export type SubjectPerformanceResponse = {
  student_id: string
  performance: SubjectPerformanceItem[]
}

// MD-03 analytics response types -------------------------------------------

export type TrendPoint = {
  semester: number
  academic_year: string | null
  sgpa: number | null
  percentage: number | null
  attendance: number | null
  result: string | null
  standing: string | null
}

export type TrendMovement = {
  available: boolean
  metric?: string | null
  previous_semester?: number | null
  current_semester?: number | null
  previous_value?: number | null
  current_value?: number | null
  delta?: number | null
  direction?: string | null
}

export type PerformanceTrends = {
  points: TrendPoint[]
  movements: Record<string, TrendMovement>
  overall_direction: string
  interpretation: string | null
}

export type StrengthItem = {
  subject_code: string
  subject_name: string
  semester: number
  percentage: number
  grade: string | null
  grade_point: number | null
  category: string
}

export type NeedsAttentionItem = {
  subject_code: string
  subject_name: string
  semester: number
  percentage: number | null
  grade: string | null
  result_status: string | null
  reason: string
  reason_code: string
  priority: number
}

export type LearningGapItem = {
  subject_code: string
  subject_name: string
  semester: number
  signal: string
  signal_code: string
  detail: string
  percentage: number | null
}

export type BenchmarkItem = {
  subject_code: string
  subject_name: string
  semester: number
  your_percentage: number
  class_average: number | null
  difference: number | null
  cohort_size: number
  available: boolean
}

export type AttemptItem = {
  attempt_number: number
  semester: number
  academic_year: string | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
}

export type AttemptHistoryItem = {
  subject_code: string
  subject_name: string
  attempts: AttemptItem[]
  has_multiple_attempts: boolean
  improvement: number | null
}

export type StudentAnalytics = {
  student_id: string
  trends: PerformanceTrends
  strengths: StrengthItem[]
  needs_attention: NeedsAttentionItem[]
  learning_gaps: LearningGapItem[]
  class_benchmark: BenchmarkItem[]
  attempt_history: AttemptHistoryItem[]
}

export type BffErrorCode =
  | "unauthorized"
  | "unlinked"
  | "unavailable"
  | "not_found"
  | "server_error"

export type BffError = {
  status: number
  code: BffErrorCode
  message: string
}

export type BffResult<T> =
  | { ok: true; data: T; fetchedAt: string }
  | { ok: false; error: BffError }

type CacheEntry = { value: unknown; expiresAt: number }

const bffCache = new Map<string, CacheEntry>()

async function getSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies()
  const raw = cookieStore.get("session")?.value
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as SessionUser
    return parsed && typeof parsed === "object" ? parsed : null
  } catch {
    return null
  }
}

function toBffError(status: number): BffError {
  switch (status) {
    case 400:
      return {
        status,
        code: "unlinked",
        message: "This account is not linked to a student record yet.",
      }
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
        message: "This account is not allowed to view student data.",
      }
    case 404:
      return {
        status,
        code: "not_found",
        message: "No academic records were found for this account.",
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
        message: "Something went wrong while loading your data.",
      }
  }
}

async function callFastapi<T>(
  path: string,
  ttlMs: number,
  options?: {
    useCache?: boolean
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
  if (user.role !== "Student") {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to view student data.",
      },
    }
  }
  if (!user.student_id) {
    return {
      ok: false,
      error: {
        status: 400,
        code: "unlinked",
        message: "This account is not linked to a student record yet.",
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
  const key = `${user.student_id}:${pathWithQuery}`
  const useCache = options?.useCache !== false

  if (useCache) {
    const hit = bffCache.get(key)
    if (hit && hit.expiresAt > Date.now()) {
      return Promise.resolve(hit.value as BffResult<T>)
    }
  }

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/students/me/${pathWithQuery}`, {
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
    if (useCache) {
      bffCache.set(key, { value: result, expiresAt: Date.now() + ttlMs })
    }
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

export function getStudentProfile(): Promise<BffResult<StudentProfile>> {
  return callFastapi<StudentProfile>("profile", BFF_TTL_MS)
}

export function getAcademicSummary(): Promise<BffResult<SemesterSummaryResponse>> {
  return callFastapi<SemesterSummaryResponse>("academic-summary", BFF_TTL_MS)
}

export function getStudentPerformance(
  semester?: number,
): Promise<BffResult<SubjectPerformanceResponse>> {
  const path = semester === undefined ? "performance" : `performance?semester=${semester}`
  return callFastapi<SubjectPerformanceResponse>(path, BFF_TTL_MS)
}

export function getStudentAnalytics(): Promise<BffResult<StudentAnalytics>> {
  return callFastapi<StudentAnalytics>("analytics", BFF_TTL_MS)
}

export type DashboardData = {
  profile: StudentProfile
  summaries: SemesterSummaryItem[]
  latestSummary: SemesterSummaryItem | null
  currentSemesterSubjects: SubjectPerformanceItem[]
}

export async function getDashboardData(): Promise<BffResult<DashboardData>> {
  const [profile, summary, performance] = await Promise.all([
    getStudentProfile(),
    getAcademicSummary(),
    getStudentPerformance(),
  ])
  if (!profile.ok) return profile
  if (!summary.ok) return summary
  if (!performance.ok) return performance

  const latestSummary =
    summary.data.summaries.length > 0
      ? summary.data.summaries.reduce((max, item) =>
        item.semester > max.semester ? item : max,
      )
      : null
  const currentSemester = profile.data.current_semester
  const fetchedAt = [profile.fetchedAt, summary.fetchedAt, performance.fetchedAt].sort().pop()!

  return {
    ok: true,
    data: {
      profile: profile.data,
      summaries: summary.data.summaries,
      latestSummary,
      currentSemesterSubjects: performance.data.performance.filter(
        (item) => item.semester === currentSemester,
      ),
    },
    fetchedAt,
  }
}

export type AttendanceData = {
  summaries: SemesterSummaryItem[]
  performance: SubjectPerformanceItem[]
}

export async function getAttendanceData(): Promise<BffResult<AttendanceData>> {
  const [summary, performance] = await Promise.all([
    getAcademicSummary(),
    getStudentPerformance(),
  ])
  if (!summary.ok) return summary
  if (!performance.ok) return performance

  return {
    ok: true,
    data: {
      summaries: summary.data.summaries,
      performance: performance.data.performance,
    },
    fetchedAt: performance.fetchedAt,
  }
}
