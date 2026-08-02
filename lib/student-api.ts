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
}

export type SemesterSummaryItem = {
  semester: number
  sgpa: number
  total_credits_earned: number
  attendance_percentage: number
  active_backlogs: number
}

export type SemesterSummaryResponse = {
  student_id: string
  summaries: SemesterSummaryItem[]
}

export type SubjectPerformanceItem = {
  semester: number
  subject_code: string
  subject_name: string
  internal_marks: number | null
  external_marks: number | null
  total_marks: number | null
  grade: string | null
  attendance_percentage: number | null
}

export type SubjectPerformanceResponse = {
  student_id: string
  performance: SubjectPerformanceItem[]
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

function cached<T>(
  key: string,
  ttlMs: number,
  load: () => Promise<BffResult<T>>,
): Promise<BffResult<T>> {
  const now = Date.now()
  const hit = bffCache.get(key)
  if (hit && hit.expiresAt > now) {
    return Promise.resolve(hit.value as BffResult<T>)
  }
  return load().then((value) => {
    if (value.ok) {
      bffCache.set(key, { value, expiresAt: now + ttlMs })
    }
    return value
  })
}

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

async function callFastapi<T>(path: string, ttlMs: number): Promise<BffResult<T>> {
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

  const key = `${user.student_id}:${path}`
  return cached(key, ttlMs, async () => {
    try {
      const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
      const res = await fetch(`${FASTAPI_URL}/api/v1/students/me/${path}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      })
      if (!res.ok) {
        return { ok: false, error: toBffError(res.status) }
      }
      const data = (await res.json()) as T
      return { ok: true, data, fetchedAt: new Date().toISOString() }
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
  })
}

export function getStudentProfile(): Promise<BffResult<StudentProfile>> {
  return callFastapi<StudentProfile>("profile", BFF_TTL_MS)
}

export function getAcademicSummary(): Promise<BffResult<SemesterSummaryResponse>> {
  return callFastapi<SemesterSummaryResponse>("academic-summary", BFF_TTL_MS)
}

export function getStudentPerformance(): Promise<BffResult<SubjectPerformanceResponse>> {
  return callFastapi<SubjectPerformanceResponse>("performance", BFF_TTL_MS)
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
