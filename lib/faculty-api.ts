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
