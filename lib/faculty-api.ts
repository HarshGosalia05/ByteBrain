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

export type FacultyProfile = {
  faculty_id: string
  faculty_code: string
  full_name: string
  gender: string | null
  department_code: number | null
  department_name: string | null
  department_full_name: string | null
  designation: string | null
  qualification: string | null
  specialization: string | null
  experience_years: number | null
  email: string | null
  phone_number: number | null
  joining_date: string | null
  employment_type: string | null
  status: string | null
}

export type DashboardSubjectSummary = {
  subject_id: string
  subject_code: string
  subject_name: string
  credits: number | null
  students: number
  average_attendance: number | null
  average_performance: number | null
}

export type NeedsAttentionItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  flags: ("performance" | "attendance")[]
  average_attendance: number | null
  average_performance: number | null
}

export type FacultyDashboardSummary = {
  faculty_id: string
  full_name: string
  designation: string | null
  department_name: string | null
  semester_no: number | null
  academic_year: string | null
  subjects: number
  students: number
  mentees: number
  average_attendance: number | null
  average_performance: number | null
  subject_breakdown: DashboardSubjectSummary[]
  needs_attention: NeedsAttentionItem[]
}

export type FacultySubjectOption = {
  subject_id: string
  subject_code: string
  subject_name: string
}

export type FacultyTermOption = {
  semester_no: number
  academic_year: string
}

export type FacultyClassesSummary = {
  total_classes: number
  total_subjects: number
  total_students: number
  current_semester: number | null
  current_academic_year: string | null
}

export type FacultyClassesFilters = {
  semesters: number[]
  academic_years: string[]
  subjects: FacultySubjectOption[]
  term_options: FacultyTermOption[]
  grades: string[]
  result_statuses: string[]
  enrollment_statuses: string[]
  attendance_ranges: string[]
  sgpa_ranges: string[]
}

export type FacultyClassCard = {
  subject_id: string
  subject_code: string
  subject_name: string
  credits: number | null
  semester_no: number
  academic_year: string
  class_strength: number
  average_attendance: number | null
  average_percentage: number | null
  highest_marks: number | null
  lowest_marks: number | null
  average_grade: string | null
  pass_percentage: number | null
}

export type FacultyClassStudentRow = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  semester_no: number
  subject_id: string
  subject_code: string
  subject_name: string
  enrollment_status: string
  first_name: string
  last_name: string
  email: string | null
  internal_marks: number | null
  external_marks: number | null
  total_marks: number | null
  grade: string | null
  attendance_percentage: number | null
  latest_sgpa: number | null
  academic_standing: string | null
}

export type FacultyAppliedFilters = {
  semester: number | null
  academic_year: string | null
  subject_id: string | null
  attendance_range: string | null
  sgpa_range: string | null
  grade: string | null
  result_status: string | null
  student_status: string | null
}

export type FacultyPagination = {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export type FacultyClassesResponse = {
  faculty_id: string
  summary: FacultyClassesSummary
  filters: FacultyClassesFilters
  applied: FacultyAppliedFilters
  class_cards: FacultyClassCard[]
  rows: FacultyClassStudentRow[]
  pagination: FacultyPagination
}

export type FacultyMenteeFilters = {
  semesters: number[]
  standings: string[]
}

export type FacultyMenteeFlagRules = {
  attendance_below: number
  backlogs_above: number
  sgpa_below: number
}

export type FacultyMenteeSummary = {
  total_mentees: number
  needs_attention: number
  good_standing: number
  average_attendance: number | null
  average_sgpa: number | null
  flag_rules: FacultyMenteeFlagRules
}

export type FacultyMenteeRow = {
  student_id: string
  enrollment_no: number
  first_name: string
  last_name: string
  email: string | null
  semester: number
  attendance_percentage: number | null
  latest_sgpa: number | null
  backlogs: number | null
  academic_standing: string | null
  flagged: boolean
  flag_reasons: string[]
}

export type FacultyMenteeAppliedFilters = {
  semester: number | null
  standing: string | null
}

export type FacultyMenteesResponse = {
  faculty_id: string
  summary: FacultyMenteeSummary
  filters: FacultyMenteeFilters
  applied: FacultyMenteeAppliedFilters
  rows: FacultyMenteeRow[]
  pagination: FacultyPagination
}

export type FacultySemesterSummaryItem = {
  semester_no: number
  semester_sgpa: number | null
  semester_attendance_percentage: number | null
  backlog_count: number | null
  academic_standing: string | null
}

export type FacultyStudentSubjectItem = {
  semester_no: number
  subject_code: string
  subject_name: string
  internal_marks: number | null
  external_marks: number | null
  total_marks: number | null
  grade: string | null
  attendance_percentage: number | null
}

export type FacultyStudentOverview = {
  student_id: string
  enrollment_no: number
  first_name: string
  last_name: string
  email: string | null
  current_semester: number | null
  latest_sgpa: number | null
  overall_attendance_percentage: number | null
  total_backlogs: number | null
  academic_standing: string | null
  relationship: string
  semester_summaries: FacultySemesterSummaryItem[]
  subject_performance: FacultyStudentSubjectItem[]
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
        message: "This account is not linked to a faculty record yet.",
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
        message: "This account is not allowed to view faculty data.",
      }
    case 404:
      return {
        status,
        code: "not_found",
        message: "No faculty records were found for this account.",
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
  if (user.role !== "Faculty") {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to view faculty data.",
      },
    }
  }
  if (!user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 400,
        code: "unlinked",
        message: "This account is not linked to a faculty record yet.",
      },
    }
  }

  const key = `${user.faculty_id}:${path}`
  return cached(key, ttlMs, async () => {
    try {
      const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
      const res = await fetch(`${FASTAPI_URL}/api/v1/faculty/${path}`, {
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

export function getFacultyProfile(): Promise<BffResult<FacultyProfile>> {
  return callFastapi<FacultyProfile>("profile", BFF_TTL_MS)
}

export function getFacultyDashboard(): Promise<BffResult<FacultyDashboardSummary>> {
  return callFastapi<FacultyDashboardSummary>("dashboard/summary", BFF_TTL_MS)
}

export function getFacultyClasses(params?: {
  semester?: number | null
  academic_year?: string | null
  subject_id?: string | null
  search?: string | null
  attendance_range?: string | null
  sgpa_range?: string | null
  grade?: string | null
  result_status?: string | null
  student_status?: string | null
  page?: number
  page_size?: number
  sort?: string
  order?: "asc" | "desc"
}): Promise<BffResult<FacultyClassesResponse>> {
  const searchParams = new URLSearchParams()
  if (params?.semester) searchParams.set("semester", params.semester.toString())
  if (params?.academic_year) searchParams.set("academic_year", params.academic_year)
  if (params?.subject_id) searchParams.set("subject_id", params.subject_id)
  if (params?.search) searchParams.set("search", params.search)
  if (params?.attendance_range) searchParams.set("attendance_range", params.attendance_range)
  if (params?.sgpa_range) searchParams.set("sgpa_range", params.sgpa_range)
  if (params?.grade) searchParams.set("grade", params.grade)
  if (params?.result_status) searchParams.set("result_status", params.result_status)
  if (params?.student_status) searchParams.set("student_status", params.student_status)
  if (params?.page) searchParams.set("page", params.page.toString())
  if (params?.page_size) searchParams.set("page_size", params.page_size.toString())
  if (params?.sort) searchParams.set("sort", params.sort)
  if (params?.order) searchParams.set("order", params.order)

  const query = searchParams.toString()
  const path = query ? `students/classes?${query}` : "students/classes"
  return callFastapi<FacultyClassesResponse>(path, BFF_TTL_MS)
}

export function getFacultyMentees(params?: {
  semester?: number | null
  standing?: string | null
  search?: string | null
  flagged_only?: boolean
  page?: number
  page_size?: number
  sort?: string
  order?: "asc" | "desc"
}): Promise<BffResult<FacultyMenteesResponse>> {
  const searchParams = new URLSearchParams()
  if (params?.semester) searchParams.set("semester", params.semester.toString())
  if (params?.standing) searchParams.set("standing", params.standing)
  if (params?.search) searchParams.set("search", params.search)
  if (params?.flagged_only) searchParams.set("flagged_only", "true")
  if (params?.page) searchParams.set("page", params.page.toString())
  if (params?.page_size) searchParams.set("page_size", params.page_size.toString())
  if (params?.sort) searchParams.set("sort", params.sort)
  if (params?.order) searchParams.set("order", params.order)

  const query = searchParams.toString()
  const path = query ? `students/mentees?${query}` : "students/mentees"
  return callFastapi<FacultyMenteesResponse>(path, BFF_TTL_MS)
}

export function getFacultyStudentOverview(
  studentId: string
): Promise<BffResult<FacultyStudentOverview>> {
  return callFastapi<FacultyStudentOverview>(`students/${studentId}/overview`, BFF_TTL_MS)
}

export type ContactUpdateInput = {
  email?: string | null
  phone_number?: number | null
}

export async function updateFacultyContact(
  input: ContactUpdateInput,
): Promise<BffResult<FacultyProfile>> {
  const user = await getSessionUser()
  if (!user || user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to update your profile.",
      },
    }
  }

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/faculty/profile`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: input.email ?? undefined,
        phone_number: input.phone_number ?? undefined,
      }),
      cache: "no-store",
    })
    if (!res.ok) {
      return { ok: false, error: toBffError(res.status) }
    }
    const data = (await res.json()) as FacultyProfile
    bffCache.delete(`${user.faculty_id}:profile`)
    bffCache.delete(`${user.faculty_id}:dashboard/summary`)
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
}
