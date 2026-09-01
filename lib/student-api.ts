import { getSessionUser, type SessionUser } from "./student-session.ts"
import type { M1V2PredictionData } from "./m1v2-prediction"
import type { M2V2PredictionData } from "./m2v2-prediction"
import type { M3V2PredictionData } from "./m3v2-prediction"

const FASTAPI_URL = (process.env.FASTAPI_URL ?? "http://localhost:8000").replace(/\/+$/, "")
const BFF_TTL_MS = 60_000

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

export type ReportCardSubject = {
  subject_code: string
  subject_name: string
  semester: number
  credits: number | null
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
  total_marks: number | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
  attempt_number: number | null
  attendance_percentage: number | null
}

export type ReportCardSemester = {
  semester: number
  academic_year: string | null
  sgpa: number | null
  semester_percentage: number | null
  semester_grade: string | null
  semester_result: string | null
  total_credits_earned: number | null
  credits_registered: number | null
  active_backlogs: number | null
  attendance_percentage: number | null
  subjects_registered: number | null
  academic_standing: string | null
  subjects: ReportCardSubject[]
}

export type ReportCardResponse = {
  student_id: string
  generated_at: string
  profile: StudentProfile
  semesters: ReportCardSemester[]
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
  | "conflict"
  | "invalid"
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
    case 409:
      return {
        status,
        code: "conflict",
        message: "A goal of this type is already active.",
      }
    case 422:
      return {
        status,
        code: "invalid",
        message: "The submitted value is not valid.",
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

type LinkedStudentUser = SessionUser & { student_id: string }

async function requireStudentApiAccess(): Promise<
  | { ok: true; user: LinkedStudentUser }
  | { ok: false; error: BffError }
> {
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
  return { ok: true, user: user as LinkedStudentUser }
}

function toQueryString(
  query: Record<string, string | number | null | undefined>,
): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) {
      params.set(key, String(value))
    }
  }
  return params.size > 0 ? `?${params.toString()}` : ""
}

async function fetchStudentApi<T>(
  user: SessionUser,
  url: string,
  cacheKey: string,
  ttlMs: number,
  useCache: boolean,
  timeoutMs = 10000,
): Promise<BffResult<T>> {
  if (useCache) {
    const hit = bffCache.get(cacheKey)
    if (hit && hit.expiresAt > Date.now()) {
      return Promise.resolve(hit.value as BffResult<T>)
    }
  }

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
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
      bffCache.set(cacheKey, { value: result, expiresAt: Date.now() + ttlMs })
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

async function callFastapi<T>(
  path: string,
  ttlMs: number,
  options?: {
    useCache?: boolean
    query?: Record<string, string | number | null | undefined>
    timeoutMs?: number
  },
): Promise<BffResult<T>> {
  const auth = await requireStudentApiAccess()
  if (!auth.ok) return auth
  const user = auth.user

  const queryString = toQueryString(options?.query ?? {})
  const pathWithQuery = `${path}${queryString}`
  return fetchStudentApi<T>(
    user,
    `${FASTAPI_URL}/api/v1/students/me/${pathWithQuery}`,
    `${user.student_id}:${pathWithQuery}`,
    ttlMs,
    options?.useCache !== false,
    options?.timeoutMs,
  )
}

async function callApiV1<T>(
  pathBuilder: (studentId: string) => string,
  ttlMs: number,
  options?: {
    useCache?: boolean
    query?: Record<string, string | number | null | undefined>
  },
): Promise<BffResult<T>> {
  const auth = await requireStudentApiAccess()
  if (!auth.ok) return auth
  const user = auth.user

  const path = pathBuilder(user.student_id)
  const queryString = toQueryString(options?.query ?? {})
  const pathWithQuery = `${path}${queryString}`
  return fetchStudentApi<T>(
    user,
    `${FASTAPI_URL}/api/v1${pathWithQuery}`,
    `${user.student_id}:${pathWithQuery}`,
    ttlMs,
    options?.useCache !== false,
  )
}

export function getStudentProfile(): Promise<BffResult<StudentProfile>> {
  return callFastapi<StudentProfile>("profile", BFF_TTL_MS)
}

export function getAcademicSummary(): Promise<BffResult<SemesterSummaryResponse>> {
  return callFastapi<SemesterSummaryResponse>("academic-summary", BFF_TTL_MS)
}

export function getReportCard(): Promise<BffResult<ReportCardResponse>> {
  return callFastapi<ReportCardResponse>("report-card", BFF_TTL_MS)
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

// ML-09 ML insights: M1-M4 predictions + ML-08 grounded explanations --------

export type MlModelKey = "m1" | "m2" | "m3" | "m4"

export type MlExplanationFactor = {
  kind: "positive" | "concern"
  source: "input" | "business_rule" | "model_metadata"
  detail: string
}

export type MlExplanationInput = {
  name: string
  value: unknown
  present: boolean
}

export type MlModelMetadata = {
  model_id: string
  model_type: string
  algorithm: string
  task: string
  target: string
}

export type MlM1Prediction = {
  student_id: string
  subject_id: string
  semester_no: number
  predicted_end_sem_marks: number
  clipped: boolean
}

export type MlM2Prediction = {
  student_id: string
  semester_no: number
  predicted_next_semester_sgpa: number
  predicted_next_semester_percentage: number
}

export type MlM3Prediction = {
  student_id: string
  semester_no: number
  is_at_risk_next_sem: 0 | 1
}

export type MlM4Prediction = {
  student_id: string
  enrollment_no: string
  full_name: string
  department_name: string
  current_semester: string | number
  career_readiness_score: number
  career_readiness_level: string
  positive_factors: string
  risk_factors: string
}

export type MlPredictionResult =
  | {
      model_id: "m1"
      predictions: MlM1Prediction[]
      input_row_count: number
      prediction_count: number
    }
  | {
      model_id: "m2"
      predictions: MlM2Prediction[]
      input_row_count: number
      prediction_count: number
    }
  | {
      model_id: "m3"
      predictions: MlM3Prediction[]
      input_row_count: number
      prediction_count: number
    }
  | {
      model_id: "m4"
      predictions: MlM4Prediction[]
      input_row_count: number
      prediction_count: number
    }

export type MlM1Explanation = {
  prediction_type: "m1"
  subject_id: string
  subject_name: string | null
  semester_no: number
  predicted_end_sem_marks: number
  clipped: boolean
  projected_percentage: number | null
  projected_band: string | null
  inputs: MlExplanationInput[]
  factors: MlExplanationFactor[]
  interpretation: string
}

export type MlM2Explanation = {
  prediction_type: "m2"
  semester_no: number
  predicted_next_semester_sgpa: number
  predicted_next_semester_percentage: number
  current_percentage: number | null
  projected_delta_percentage: number | null
  inputs: MlExplanationInput[]
  factors: MlExplanationFactor[]
  interpretation: string
}

export type MlM3Explanation = {
  prediction_type: "m3"
  risk_scope: string
  risk_label: 0 | 1
  inputs: MlExplanationInput[]
  factors: MlExplanationFactor[]
  suggestions: string[]
  interpretation: string
}

export type MlM4Explanation = {
  prediction_type: "m4"
  readiness_score: number
  readiness_level: string
  positive_factors: string[]
  risk_factors: string[]
  inputs: MlExplanationInput[]
  interpretation: string
}

export type MlExplanationResult = {
  model_id: MlModelKey
  prediction_type: MlModelKey
  student_id: string
  explanation_kind: string
  model_metadata: MlModelMetadata
  model_version: string | null
  not_supported: string[]
  rule_context: Record<string, unknown>
  explanations: unknown[]
}

export type MlModelInsight =
  | {
      available: true
      prediction: MlPredictionResult
      explanation: MlExplanationResult
    }
  | { available: false; reason: "no_data" | "error" | "blocked"; message: string }

export type StudentMlInsights = {
  student_id: string
  generated_at: string
  models: Record<MlModelKey, MlModelInsight>
}

export function getStudentMlInsights(): Promise<BffResult<StudentMlInsights>> {
  return callApiV1<StudentMlInsights>(
    (studentId) => `/predict/insights/${encodeURIComponent(studentId)}`,
    BFF_TTL_MS,
  )
}

// M1 V2 — Subject Marks Prediction (validated production model).
// README: reuses /predict/m1v2/{student_id}; readiness_status of NO_DATA is
// surfaced by the backend as a 404 on this per-student route.

export function getStudentM1V2(): Promise<BffResult<M1V2PredictionData>> {
  return callApiV1<M1V2PredictionData>(
    (studentId) => `/predict/m1v2/${encodeURIComponent(studentId)}`,
    BFF_TTL_MS,
  )
}

// M2 V2 — Next-Semester Performance Prediction (validated production model).
// README: reuses /predict/m2v2/{student_id}; readiness_status of NO_DATA
// (including the deployment boundary — the current cohort is in the final /
// internship semester with no upcoming NORMAL academic semester) is surfaced by
// the backend as a 404 on this per-student route.

export function getStudentM2V2(): Promise<BffResult<M2V2PredictionData>> {
  return callApiV1<M2V2PredictionData>(
    (studentId) => `/predict/m2v2/${encodeURIComponent(studentId)}`,
    BFF_TTL_MS,
  )
}

// M3 V2 — At-Risk Student Prediction (validated production model).
// README: reuses /predict/m3v2/{student_id}. probability_at_risk is a model
// ESTIMATE, never a guarantee. readiness_status of NO_DATA (including the
// deployment boundary — the current cohort is in the final / internship
// semester with no upcoming NORMAL academic semester) is surfaced by the
// backend as a 404 on this per-student route.

export function getStudentM3V2(): Promise<BffResult<M3V2PredictionData>> {
  return callApiV1<M3V2PredictionData>(
    (studentId) => `/predict/m3v2/${encodeURIComponent(studentId)}`,
    BFF_TTL_MS,
  )
}

// MD-06 career guidance: verified coach data + deterministic mapping + G0 GenAI

export type CareerCoachReadiness = {
  available: boolean
  score: number | null
  level: string | null
  positive_factors: string[]
  risk_factors: string[]
  disclaimer: string | null
}

export type CareerDirection = {
  available: boolean
  domain: string | null
  source: "declared_preference" | "mapped_subject_evidence" | "unavailable"
  matched_count: number
  note: string | null
}

export type SkillEvidenceItem = {
  skill: string
  evidence: "inferred_from_subject"
  source_subject: string | null
  detail: string | null
}

export type PrioritySkillGap = {
  rank: number
  skill_area: string
  priority: "High" | "Medium"
  detail: string
  evidence: "not_verified"
}

export type CareerRoadmapStep = {
  sequence: number
  focus_area: string
  current_evidence: string
  priority: "High" | "Medium" | "Low"
  recommended_step: string
  milestone: string
  next_action: string
  progress_tracking: "available" | "not_available"
  evidence: string
}

export type CareerAiGuidance = {
  available: boolean
  content: string | null
  provider: string | null
  model: string | null
  error: "unavailable" | "rate_limited" | "timeout" | null
}

export type StudentCareerGuidance = {
  student_id: string
  data_available: boolean
  career_preferences_available: boolean
  career_readiness: CareerCoachReadiness
  career_direction: CareerDirection
  skill_strengths: SkillEvidenceItem[]
  skill_gaps: PrioritySkillGap[]
  roadmap: CareerRoadmapStep[]
  ai_guidance: CareerAiGuidance
  source: string
  generated_at: string
}

export function getStudentCareerGuidance(): Promise<
  BffResult<StudentCareerGuidance>
> {
  // Grounded GenAI generation can take longer than plain academic reads;
  // mirror the chat timeout instead of the default 10s.
  return callFastapi<StudentCareerGuidance>("career/guidance", BFF_TTL_MS, {
    timeoutMs: 30000,
  })
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

// MD-04 attendance what-if simulator -----------------------------------------

export type AttendanceSimulatorSubject = {
  subject_id: string
  subject_code: string | null
  subject_name: string
  credits: number | null
  total_classes: number | null
  attended_classes: number | null
  attendance_percentage: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
}

export type AttendanceWhatIfSimulation = {
  subject_id: string
  subject_code: string | null
  subject_name: string
  total_classes: number
  attended_classes: number
  hypothetical_present: number
  hypothetical_absent: number
  current_attendance: number | null
  resulting_attendance: number | null
  delta: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
  target_attendance: number
  at_target: boolean
  classes_to_reach_target: number | null
  classes_to_skip_below_target: number | null
  complete: boolean
  message: string | null
}

export type AttendanceWhatIfData = {
  student_id: string
  context: {
    student_id: string
    target_attendance: number
    subjects: AttendanceSimulatorSubject[]
  }
  simulation: AttendanceWhatIfSimulation | null
}

export function getAttendanceWhatIf(): Promise<BffResult<AttendanceWhatIfData>> {
  return callFastapi<AttendanceWhatIfData>("analytics/attendance-what-if", BFF_TTL_MS)
}

// MD-04 daily assistant + timetable types ------------------------------------

export type StudentTimetableSession = {
  timetable_id: number
  day_name: string
  slot_no: number
  start_time: string
  end_time: string
  subject_id: string
  subject_code: string | null
  subject_name: string
  credits: number | null
  lecture_type: string | null
  faculty_id: string | null
  faculty_name: string | null
}

export type StudentTimetableDay = {
  day_name: string
  sessions: StudentTimetableSession[]
}

export type StudentTimetableSlot = {
  slot_no: number
  start_time: string
  end_time: string
}

export type StudentTimetableResponse = {
  student_id: string
  semester_no: number
  academic_year: string
  department_name: string | null
  total_sessions: number
  slots: StudentTimetableSlot[]
  days: StudentTimetableDay[]
}

export type DailyClass = {
  subject_id: string
  subject_code: string | null
  subject_name: string
  slot_no: number
  start_time: string
  end_time: string
  lecture_type: string | null
  credits: number | null
  faculty_name: string | null
  attendance_percentage: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
  performance_percentage: number | null
  recorded_statuses: string[]
  recorded: boolean
}

export type FreeSlot = {
  slot_no: number
  start_time: string
  end_time: string
}

export type NextClass = {
  day_name: string
  is_tomorrow: boolean
  subject_id: string
  subject_code: string | null
  subject_name: string
  slot_no: number
  start_time: string
  end_time: string
  attendance_percentage: number | null
}

export type ClassCountByDay = {
  day_name: string
  count: number
}

export type StudyPriority = {
  priority: number
  priority_label: string
  subject_id: string
  subject_code: string | null
  subject_name: string
  attendance_percentage: number | null
  performance_percentage: number | null
  shortage_flag: string | null
  eligibility_status: string | null
  reasons: string[]
  required_classes_to_reach_target: number | null
  target_attendance: number
}

export type DailyPriority = {
  priority: number
  text: string
}

export type UpcomingDay = {
  day_name: string
  is_tomorrow: boolean
  sessions: StudentTimetableSession[]
}

export type TermContext = {
  semester_no: number
  academic_year: string
  department_name: string | null
  timetable_available: boolean
}

export type AttendanceContext = {
  semester_overall_attendance: number | null
  stored_overall_attendance: number | null
  note: string
}

export type Deferral = {
  feature: string
  status: string
  note: string
}

export type DailyAssistantResponse = {
  student_id: string
  date: string
  day_name: string
  day_source: string
  is_focus_today: boolean
  term: TermContext | null
  today_classes: DailyClass[]
  next_class: NextClass | null
  free_slots: FreeSlot[]
  classes_per_day: ClassCountByDay[]
  study_priorities: StudyPriority[]
  daily_priorities: DailyPriority[]
  upcoming_classes: UpcomingDay[]
  attendance_context: AttendanceContext
  deferrals: Deferral[]
}

export function getStudentTimetable(): Promise<BffResult<StudentTimetableResponse>> {
  return callFastapi<StudentTimetableResponse>("timetable", BFF_TTL_MS)
}

export function getDailyAssistant(
  date?: string,
): Promise<BffResult<DailyAssistantResponse>> {
  const path = date ? `daily-assistant?date=${date}` : "daily-assistant"
  return callFastapi<DailyAssistantResponse>(path, BFF_TTL_MS)
}

// MD-05 health score / priorities / goals / notifications --------------------

export type HealthComponent = {
  available: boolean
  score: number | null
  weight: number
  reason: string
}

export type HealthScoreResponse = {
  student_id: string
  available: boolean
  score: number | null
  band: string | null
  components: Record<string, HealthComponent>
  reasons: string[]
  generated_at: string
}

export type PriorityItem = {
  rank: number
  signal: string
  severity: number
  title: string
  reason: string
  action: string
  subject: string | null
  metric: string | null
}

export type PrioritiesResponse = {
  student_id: string
  items: PriorityItem[]
}

export type GoalType = "target_sgpa" | "target_percentage" | "target_attendance"

export type StudentGoal = {
  goal_id: string
  goal_type: string
  target_value: number
  current_value: number | null
  achieved: boolean | null
  status: string
  created_at: string
  updated_at: string
}

export type GoalsResponse = {
  student_id: string
  goals: StudentGoal[]
}

export type GoalCreateInput = {
  goal_type: GoalType
  target_value: number
}

export type GoalUpdateInput = {
  target_value?: number | null
  status?: "Active" | "Inactive" | null
}

export type NotificationTypeFilter =
  | "ATTENDANCE_WARNING"
  | "ELIGIBILITY_WARNING"
  | "MARKS_PUBLISHED"
  | "MARKS_UPDATED"
  | "MARKS_CLEARED"
  | "PERFORMANCE_CHANGE"
  | "RISK_ALERT"
  | "TIMETABLE_CHANGE"
  | "SYSTEM"

export type NotificationItem = {
  message_id: string
  message_type: string
  title: string
  message_body: string
  subject: string | null
  priority: string
  status: string
  created_at: string
}

export type NotificationsResponse = {
  student_id: string
  items: NotificationItem[]
  total: number
  page: number
  page_size: number
  unread_count: number
}

export type UnreadCountResponse = {
  student_id: string
  unread_count: number
}

export type MarkAllReadResponse = {
  student_id: string
  updated_count: number
}

export type ClearAllResponse = {
  student_id: string
  cleared_count: number
}

export function invalidateBffKeys(studentId: string, prefixes: string[]) {
  const base = `${studentId}:`
  for (const key of Array.from(bffCache.keys())) {
    if (prefixes.some((p) => key.startsWith(`${base}${p}`))) {
      bffCache.delete(key)
    }
  }
}

async function mutateStudent<T>(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  body: unknown,
  invalidatePrefixes: string[],
): Promise<BffResult<T>> {
  const user = await getSessionUser()
  if (!user) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to make changes.",
      },
    }
  }
  if (user.role !== "Student" || !user.student_id) {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to make changes.",
      },
    }
  }
  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/students/me/${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    if (!res.ok) {
      if (res.status === 400) {
        const errJson = (await res.json().catch(() => null)) as { detail?: string } | null
        return {
          ok: false,
          error: {
            status: 400,
            code: "invalid",
            message: typeof errJson?.detail === "string" ? errJson.detail : "Invalid request.",
          },
        }
      }
      return { ok: false, error: toBffError(res.status) }
    }
    const data = (await res.json()) as T
    invalidateBffKeys(user.student_id, invalidatePrefixes)
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

export function getHealthScore(): Promise<BffResult<HealthScoreResponse>> {
  return callFastapi<HealthScoreResponse>("health-score", BFF_TTL_MS)
}

export function getPriorities(): Promise<BffResult<PrioritiesResponse>> {
  return callFastapi<PrioritiesResponse>("priorities", BFF_TTL_MS)
}

export function getGoals(): Promise<BffResult<GoalsResponse>> {
  return callFastapi<GoalsResponse>("goals", BFF_TTL_MS)
}

export function getGoal(goalId: string): Promise<BffResult<StudentGoal>> {
  return callFastapi<StudentGoal>(`goals/${goalId}`, BFF_TTL_MS)
}

export function createGoal(input: GoalCreateInput): Promise<BffResult<StudentGoal>> {
  return mutateStudent<StudentGoal>("goals", "POST", input, ["goals"])
}

export function updateGoal(
  goalId: string,
  input: GoalUpdateInput,
): Promise<BffResult<StudentGoal>> {
  return mutateStudent<StudentGoal>(`goals/${goalId}`, "PATCH", input, ["goals"])
}

export function getNotifications(
  options?: {
    messageType?: NotificationTypeFilter
    unreadOnly?: boolean
    page?: number
    pageSize?: number
  },
): Promise<BffResult<NotificationsResponse>> {
  return callFastapi<NotificationsResponse>("notifications", BFF_TTL_MS, {
    useCache: false,
    query: {
      message_type: options?.messageType,
      unread_only: options?.unreadOnly === true ? "true" : undefined,
      page: options?.page,
      page_size: options?.pageSize,
    },
  })
}

export function getUnreadNotificationCount(): Promise<BffResult<UnreadCountResponse>> {
  return callFastapi<UnreadCountResponse>("notifications/unread-count", BFF_TTL_MS, {
    useCache: false,
  })
}

export function markNotificationRead(
  messageId: string,
): Promise<BffResult<NotificationItem>> {
  return mutateStudent<NotificationItem>(
    `notifications/${messageId}/read`,
    "PATCH",
    {},
    ["notifications"],
  )
}

export function markAllNotificationsRead(): Promise<BffResult<MarkAllReadResponse>> {
  return mutateStudent<MarkAllReadResponse>("notifications/read-all", "POST", {}, ["notifications"])
}

export function clearNotification(
  messageId: string,
): Promise<BffResult<NotificationItem>> {
  return mutateStudent<NotificationItem>(
    `notifications/${messageId}`,
    "DELETE",
    {},
    ["notifications"],
  )
}

export function clearAllNotifications(): Promise<BffResult<ClearAllResponse>> {
  return mutateStudent<ClearAllResponse>("notifications", "DELETE", {}, ["notifications"])
}

export type StudentHealthData = {
  profile: StudentProfile
  health: HealthScoreResponse
  priorities: PrioritiesResponse
  goals: GoalsResponse
  unreadCount: number
}

export async function getStudentHealthData(): Promise<BffResult<StudentHealthData>> {
  const [profile, health, priorities, goals, unread] = await Promise.all([
    getStudentProfile(),
    getHealthScore(),
    getPriorities(),
    getGoals(),
    getUnreadNotificationCount(),
  ])
  if (!profile.ok) return profile
  if (!health.ok) return health
  if (!priorities.ok) return priorities
  if (!goals.ok) return goals
  if (!unread.ok) return unread
  return {
    ok: true,
    data: {
      profile: profile.data,
      health: health.data,
      priorities: priorities.data,
      goals: goals.data,
      unreadCount: unread.data.unread_count,
    },
    fetchedAt: health.fetchedAt,
  }
}

export type StudentSettingsResponse = {
  namespaces: {
    account?: {
      display_language?: "en" | "hi" | "gu"
      name_display?: "full_name" | "first_name" | "formal" | "with_id"
      [key: string]: unknown
    }
    notifications?: {
      grade_alerts?: boolean
      attendance_warnings?: boolean
      semester_results?: boolean
      digest_frequency?: string
      browser_enabled?: boolean
      [key: string]: unknown
    }
    security?: {
      two_factor_enabled?: boolean
      two_factor_method?: string
      two_factor_updated_at?: string
      password_updated_at?: string
      last_login?: string
      last_sign_out_all?: string
      sessions?: unknown[]
      [key: string]: unknown
    }
    [key: string]: Record<string, unknown> | undefined
  }
  metadata: {
    schema_version: number
    preference_version: number
    configuration_version: number
    last_modified?: string | null
    last_synced?: string | null
  }
  activity: Array<{
    event: string
    at: string
    namespace?: string | null
    detail?: string | null
  }>
}

export type StudentSettingsUpdateResponse = {
  namespaces: Record<string, Record<string, unknown>>
  metadata: Record<string, unknown>
  activity: unknown[]
  highlights: string[]
}

export type SecurityActionResult = {
  status: string
  message: string
  timestamp?: string
  two_factor_enabled?: boolean
  two_factor_method?: string
}

export function getStudentSettings(): Promise<BffResult<StudentSettingsResponse>> {
  return callFastapi<StudentSettingsResponse>("settings", BFF_TTL_MS)
}

export async function updateStudentSettings(
  namespace: string,
  patch: Record<string, unknown>,
): Promise<BffResult<StudentSettingsUpdateResponse>> {
  const result = await mutateStudent<StudentSettingsUpdateResponse>(
    `settings/${namespace}`,
    "PATCH",
    patch,
    ["settings"],
  )
  if (result.ok) {
    bffCache.delete("settings")
  }
  return result
}

export async function changeStudentPassword(
  currentPassword: string,
  newPassword: string,
): Promise<BffResult<SecurityActionResult>> {
  return mutateStudent<SecurityActionResult>(
    "settings/change-password",
    "POST",
    { current_password: currentPassword, new_password: newPassword },
    ["settings"],
  )
}

export async function setStudentTwoFactor(
  enabled: boolean,
  method: string = "email",
): Promise<BffResult<SecurityActionResult>> {
  return mutateStudent<SecurityActionResult>(
    "settings/two-factor",
    "POST",
    { enabled, method },
    ["settings"],
  )
}

export async function signOutAllStudentDevices(): Promise<BffResult<SecurityActionResult>> {
  return mutateStudent<SecurityActionResult>(
    "settings/sign-out-all",
    "POST",
    {},
    ["settings"],
  )
}
