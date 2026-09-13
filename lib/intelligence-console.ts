import { getSessionUser, getSessionToken } from "./auth-jwt"
import type { StudentProfile, SemesterSummaryItem, StudentCareerGuidance } from "./student-api"
import type { M1V3PredictionData } from "./m1v3-prediction"
import type { M3V2PredictionData } from "./m3v2-prediction"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")

export type SystemHealthStatus = {
  backend: "healthy" | "degraded" | "unavailable"
  database: "connected" | "unavailable"
  checkedAt: string
}

export type IntelligenceConsoleData = {
  profile: StudentProfile
  latestSummary: SemesterSummaryItem | null
  m1v3: M1V3PredictionData | null
  m3v2: M3V2PredictionData | null
  m4Score: { score: number | null; level: string | null } | null
  careerGuidance: StudentCareerGuidance | null
  systemHealth: SystemHealthStatus
}

async function fetchWithAuth<T>(
  url: string,
  token: string,
  timeoutMs = 5000,
): Promise<T | null> {
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | null> {
  return Promise.race([
    promise,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), ms)),
  ])
}

export async function fetchIntelligenceConsoleData(): Promise<{
  ok: true
  data: IntelligenceConsoleData
} | { ok: false; reason: string }> {
  try {
    const user = await getSessionUser()
    if (!user || user.role !== "Student" || !user.student_id) {
      return { ok: false, reason: "not_authenticated" }
    }

    const token = (await getSessionToken()) ?? ""
    const sid = encodeURIComponent(user.student_id)

    const results = await withTimeout(
      Promise.all([
        fetchWithAuth<{ first_name: string; last_name: string; enrollment_no: number; current_semester: number; department_name: string | null; overall_cgpa: number | null; latest_sgpa: number | null; total_backlogs: number | null; academic_standing: string | null; total_credits_earned: number | null }>(
          `${FASTAPI_URL}/api/v1/students/me/profile`,
          token,
          5000,
        ),
        fetchWithAuth<{ summaries: SemesterSummaryItem[] }>(
          `${FASTAPI_URL}/api/v1/students/me/academic-summary`,
          token,
          5000,
        ),
        fetchWithAuth<M1V3PredictionData>(
          `${FASTAPI_URL}/api/v1/predict/m1v3/${sid}`,
          token,
          8000,
        ),
        fetchWithAuth<M3V2PredictionData>(
          `${FASTAPI_URL}/api/v1/predict/m3v2/${sid}`,
          token,
          8000,
        ),
        fetchWithAuth<{ career_readiness_score: number | null; career_readiness_level: string | null }>(
          `${FASTAPI_URL}/api/v1/predict/m4/${sid}`,
          token,
          8000,
        ),
        fetchWithAuth<StudentCareerGuidance>(
          `${FASTAPI_URL}/api/v1/students/me/career/guidance`,
          token,
          8000,
        ),
        fetchWithAuth<SystemHealthStatus>(
          `${FASTAPI_URL}/api/v1/health`,
          token,
          3000,
        ),
      ]),
      10000,
    )

    if (!results) {
      return { ok: false, reason: "timeout" }
    }

    const [profile, academicSummary, m1v3, m3v2, m4Result, careerGuidance, systemHealth] = results

    if (!profile) {
      return { ok: false, reason: "profile_unavailable" }
    }

    const summaries = academicSummary?.summaries ?? []
    const latestSummary =
      summaries.length > 0
        ? summaries.reduce((max, item) => (item.semester > max.semester ? item : max))
        : null

    return {
      ok: true,
      data: {
        profile: profile as StudentProfile,
        latestSummary,
        m1v3: m1v3 ?? null,
        m3v2: m3v2 ?? null,
        m4Score: m4Result
          ? { score: m4Result.career_readiness_score, level: m4Result.career_readiness_level }
          : null,
        careerGuidance: careerGuidance ?? null,
        systemHealth: systemHealth ?? {
          backend: "unavailable",
          database: "unavailable",
          checkedAt: new Date().toISOString(),
        },
      },
    }
  } catch {
    return { ok: false, reason: "fetch_failed" }
  }
}
