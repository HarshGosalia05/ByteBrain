import { getSessionUser } from "./student-session.ts"

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

export type FacultyStudentProfileStudent = {
  student_id: string
  enrollment_no: number
  university_roll_no: string | null
  first_name: string
  last_name: string
  full_name: string
  gender: string | null
  date_of_birth: string | null
  category: string | null
  admission_year: number | null
  admission_date: string | null
  admission_type: string | null
  admission_quota: string | null
  department_name: string | null
  current_semester: number | null
  current_academic_year: string | null
  city: string | null
  email: string | null
  student_phone_number: number | null
  guardian_name: string | null
  guardian_phone: number | null
  student_status: string | null
  latest_sgpa: number | null
  overall_cgpa: number | null
  overall_percentage: number | null
  overall_attendance_percentage: number | null
  total_credits_registered: number | null
  total_credits_earned: number | null
  total_backlogs: number | null
  academic_standing: string | null
}

export type FacultyStudentProfileMentor = {
  faculty_name: string | null
  designation: string | null
  mentor_role: string | null
  mentor_since: string | null
}

export type FacultyStudentProfileSemester = {
  semester_no: number
  academic_year: string | null
  subjects_registered: number | null
  credits_registered: number | null
  credits_earned: number | null
  semester_percentage: number | null
  semester_sgpa: number | null
  semester_grade: string | null
  semester_attendance_percentage: number | null
  backlog_count: number | null
  semester_result: string | null
  academic_standing: string | null
}

export type FacultyStudentProfileSubject = {
  semester_no: number
  academic_year: string | null
  subject_id: string
  subject_code: string
  subject_name: string
  credits: number | null
  subject_type: string | null
  faculty_id: string | null
  faculty_name: string | null
  internal_marks: number | null
  mid_sem_marks: number | null
  external_marks: number | null
  total_marks: number | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
  attempt_number: number | null
  total_classes: number | null
  attended_classes: number | null
  attendance_percentage: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
}

export type FacultyStudentProfileCareer = {
  preferred_domain: string | null
  dream_job_role: string | null
  preferred_industry: string | null
  preferred_work_mode: string | null
  target_package_lpa: number | null
  higher_studies_interest: string | null
  entrepreneurship_interest: string | null
  certification_interest: string | null
  internship_completed: string | null
  placement_readiness_level: string | null
}

export type FacultyStudentProfileView = {
  student: FacultyStudentProfileStudent
  relationship: string
  mentor: FacultyStudentProfileMentor | null
  rank: number | null
  rank_total: number | null
  message_count: number
  semester_summaries: FacultyStudentProfileSemester[]
  subject_performance: FacultyStudentProfileSubject[]
  career: FacultyStudentProfileCareer | null
}

export type FacultySubjectsSummary = {
  total_subjects: number
  total_students: number
  current_semester: number | null
  current_academic_year: string | null
  average_attendance: number | null
  average_performance: number | null
}

export type FacultySubjectsFilters = {
  semesters: number[]
  academic_years: string[]
  batches?: string[]
}

export type FacultySubjectsAppliedFilters = {
  semester: number | null
  academic_year: string | null
  search: string | null
  batch?: string | null
}

export type FacultySubjectsResponse = {
  faculty_id: string
  summary: FacultySubjectsSummary
  filters: FacultySubjectsFilters
  applied: FacultySubjectsAppliedFilters
  cards: FacultyClassCard[]
  pagination: FacultyPagination
}

export type FacultySubjectGradeItem = {
  grade: string
  count: number
}

export type FacultySubjectAttendanceItem = {
  band: string
  count: number
}

export type FacultySubjectEnrolledStudent = {
  student_id: string
  enrollment_no: number
  first_name: string
  last_name: string
  attendance_percentage: number | null
  total_marks: number | null
  grade: string | null
}

export type FacultySubjectLearningGap = {
  flagged: boolean
  reason: string | null
  threshold: number
  average_performance: number | null
}

export type FacultySubjectSummary = {
  total_enrolled: number
  average_percentage: number | null
  average_attendance: number | null
  pass_percentage: number | null
  average_grade: string | null
}

export type FacultySubjectDetail = {
  subject_id: string
  subject_code: string
  subject_name: string
  credits: number | null
  semester_no: number
  academic_year: string
  subject_type: string | null
  assessment_type: string | null
  department_name: string | null
  summary: FacultySubjectSummary
  grade_distribution: FacultySubjectGradeItem[]
  attendance_distribution: FacultySubjectAttendanceItem[]
  learning_gap: FacultySubjectLearningGap
  enrolled_students: FacultySubjectEnrolledStudent[]
}

export type FacultySubjectHistoryItem = {
  semester_no: number
  academic_year: string
  students: number
  average_performance: number | null
  average_attendance: number | null
  pass_percentage: number | null
}

export type FacultySubjectHistory = {
  subject_id: string
  subject_code: string
  subject_name: string
  current_semester: number | null
  current_academic_year: string | null
  semesters_taught: FacultySubjectHistoryItem[]
}

export type BffErrorCode =
  | "unauthorized"
  | "unlinked"
  | "unavailable"
  | "not_found"
  | "empty"
  | "server_error"
  | "invalid"
  | "conflict"

export type BffError = {
  status: number
  code: BffErrorCode
  message: string
}

export type BffResult<T> =
  | { ok: true; data: T; fetchedAt: string }
  | { ok: false; error: BffError }

type CacheEntry = { value: unknown; expiresAt: number }

const globalBffCache = globalThis as typeof globalThis & {
  bffCache?: Map<string, CacheEntry>
}
const bffCache = globalBffCache.bffCache ?? (globalBffCache.bffCache = new Map<string, CacheEntry>())

function cached<T>(
  key: string,
  ttlMs: number,
  load: () => Promise<BffResult<T>>,
  bypassCache = false,
): Promise<BffResult<T>> {
  const now = Date.now()
  if (!bypassCache) {
    const hit = bffCache.get(key)
    if (hit && hit.expiresAt > now) {
      return Promise.resolve(hit.value as BffResult<T>)
    }
  }
  return load().then((value) => {
    if (value.ok) {
      bffCache.set(key, { value, expiresAt: now + ttlMs })
    }
    return value
  })
}

function toBffError(status: number, customDetail?: string): BffError {
  if (customDetail && typeof customDetail === "string" && customDetail.trim()) {
    const code: BffErrorCode =
      status >= 500
        ? "server_error"
        : status === 404
          ? "not_found"
          : status === 403 || status === 401
            ? "unauthorized"
            : status === 409
              ? "conflict"
              : status === 422
                ? "invalid"
                : "unavailable"
    return {
      status,
      code,
      message: customDetail.trim(),
    }
  }
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
    case 409:
      return {
        status,
        code: "conflict",
        message: "This record already exists. Refresh and try again.",
      }
    case 422:
      return {
        status,
        code: "invalid",
        // Deliberately module-neutral: FastAPI's 422 can be produced by any
        // request-validation failure (e.g. an invalid query parameter). It must
        // NOT carry Marks-specific wording, which previously leaked into
        // Attendance Entry whenever an attendance call returned 422.
        message: "The submitted request was rejected because one or more values were invalid. Please review your input and try again.",
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
  bypassCache = false,
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
  return cached(
    key,
    ttlMs,
    async () => {
      try {
        const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
        const res = await fetch(`${FASTAPI_URL}/api/v1/faculty/${path}`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        })
        if (!res.ok) {
          let customDetail: string | undefined
          try {
            const errBody = await res.json()
            if (typeof errBody?.detail === "string" && errBody.detail.trim()) {
              customDetail = errBody.detail
            } else if (typeof errBody?.message === "string" && errBody.message.trim()) {
              customDetail = errBody.message
            }
          } catch {}
          return { ok: false, error: toBffError(res.status, customDetail) }
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
    },
    bypassCache,
  )
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

export function getFacultyStudentProfile(
  studentId: string
): Promise<BffResult<FacultyStudentProfileView>> {
  return callFastapi<FacultyStudentProfileView>(`students/${studentId}/profile`, BFF_TTL_MS)
}

// ML-10 Faculty ML insights: M1-M4 predictions + ML-08 grounded explanations -----

export type FacultyMlModelKey = "m1" | "m2" | "m3" | "m4"

export type FacultyMlExplanationFactor = {
  kind: "positive" | "concern"
  source: "input" | "business_rule" | "model_metadata"
  detail: string
}

export type FacultyMlExplanationInput = {
  name: string
  value: unknown
  present: boolean
}

export type FacultyMlModelMetadata = {
  model_id: string
  model_type: string
  algorithm: string
  task: string
  target: string
}

export type FacultyMlM1Prediction = {
  student_id: string
  subject_id: string
  semester_no: number
  predicted_end_sem_marks: number
  clipped: boolean
}

export type FacultyMlM2Prediction = {
  student_id: string
  semester_no: number
  predicted_next_semester_sgpa: number
  predicted_next_semester_percentage: number
}

export type FacultyMlM3Prediction = {
  student_id: string
  semester_no: number
  is_at_risk_next_sem: 0 | 1
}

export type FacultyMlM4Prediction = {
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

export type FacultyMlPredictionResult =
  | {
      model_id: "m1"
      predictions: FacultyMlM1Prediction[]
      input_row_count: number
      prediction_count: number
    }
  | {
      model_id: "m2"
      predictions: FacultyMlM2Prediction[]
      input_row_count: number
      prediction_count: number
    }
  | {
      model_id: "m3"
      predictions: FacultyMlM3Prediction[]
      input_row_count: number
      prediction_count: number
    }
  | {
      model_id: "m4"
      predictions: FacultyMlM4Prediction[]
      input_row_count: number
      prediction_count: number
    }

export type FacultyMlM1Explanation = {
  prediction_type: "m1"
  subject_id: string
  subject_name: string | null
  semester_no: number
  predicted_end_sem_marks: number
  clipped: boolean
  projected_percentage: number | null
  projected_band: string | null
  inputs: FacultyMlExplanationInput[]
  factors: FacultyMlExplanationFactor[]
  interpretation: string
}

export type FacultyMlM2Explanation = {
  prediction_type: "m2"
  semester_no: number
  predicted_next_semester_sgpa: number
  predicted_next_semester_percentage: number
  current_percentage: number | null
  projected_delta_percentage: number | null
  inputs: FacultyMlExplanationInput[]
  factors: FacultyMlExplanationFactor[]
  interpretation: string
}

export type FacultyMlM3Explanation = {
  prediction_type: "m3"
  risk_scope: string
  risk_label: 0 | 1
  inputs: FacultyMlExplanationInput[]
  factors: FacultyMlExplanationFactor[]
  suggestions: string[]
  interpretation: string
}

export type FacultyMlM4Explanation = {
  prediction_type: "m4"
  readiness_score: number
  readiness_level: string
  positive_factors: string[]
  risk_factors: string[]
  inputs: FacultyMlExplanationInput[]
  interpretation: string
}

export type FacultyMlExplanationResult = {
  model_id: FacultyMlModelKey
  prediction_type: FacultyMlModelKey
  student_id: string
  explanation_kind: string
  model_metadata: FacultyMlModelMetadata
  model_version: string | null
  not_supported: string[]
  rule_context: Record<string, unknown>
  explanations: unknown[]
}

export type FacultyMlModelInsight =
  | {
      available: true
      prediction: FacultyMlPredictionResult
      explanation: FacultyMlExplanationResult
    }
  | { available: false; reason: "no_data" | "error" | "blocked"; message: string }

export type FacultyStudentMlInsights = {
  student_id: string
  generated_at: string
  models: Record<FacultyMlModelKey, FacultyMlModelInsight>
}

// =============================================================================
// ML-12 Faculty Feedback Loop — BFF layer
// =============================================================================

export type FacultyFeedbackAction = "confirmed" | "dismissed"

export type FacultyFeedbackItem = {
  feedback_id: string
  prediction_id: string
  student_id: string
  faculty_id: string
  feedback_action: FacultyFeedbackAction
  note: string | null
  model_version: string | null
  feedback_timestamp: string
}

export type FacultyLatestM3Prediction = {
  prediction_id: string
  model_version: string | null
  generated_at: string
  is_at_risk_next_sem: 0 | 1
  risk_probability: number | null
}

export type FacultyStudentFeedbackContext = {
  student_id: string
  latest_m3_prediction: FacultyLatestM3Prediction | null
  current_verdict: FacultyFeedbackItem | null
  feedback_history: FacultyFeedbackItem[]
}

export type FacultyPredictionFeedbackDetail = {
  prediction_id: string
  student_id: string
  prediction_type: string
  current_verdict: FacultyFeedbackItem | null
  feedback_history: FacultyFeedbackItem[]
}

export function getStudentPredictionFeedbackContext(
  studentId: string
): Promise<BffResult<FacultyStudentFeedbackContext>> {
  return callFastapi<FacultyStudentFeedbackContext>(
    `students/${encodeURIComponent(studentId)}/feedback`,
    BFF_TTL_MS,
  )
}

export function getPredictionFeedback(
  predictionId: string
): Promise<BffResult<FacultyPredictionFeedbackDetail>> {
  return callFastapi<FacultyPredictionFeedbackDetail>(
    `predictions/${encodeURIComponent(predictionId)}/feedback`,
    BFF_TTL_MS,
  )
}

export function submitPredictionFeedback(
  predictionId: string,
  payload: { action: FacultyFeedbackAction; note?: string | null },
  studentId: string,
): Promise<BffResult<FacultyFeedbackItem>> {
  return mutateFastapi<FacultyFeedbackItem>(
    `predictions/${encodeURIComponent(predictionId)}/feedback`,
    "POST",
    {
      action: payload.action,
      // Missing or blank notes are sent as NULL (never an empty string), matching
      // the ML-12 contract that absent context stays absent.
      note:
        typeof payload.note === "string" && payload.note.trim() ? payload.note : null,
    },
    [`students/${encodeURIComponent(studentId)}/feedback`],
  )
}

export function getFacultyStudentMlInsights(
  studentId: string
): Promise<BffResult<FacultyStudentMlInsights>> {
  return callFastapi<FacultyStudentMlInsights>(
    `students/${encodeURIComponent(studentId)}/ml-insights`,
    BFF_TTL_MS,
  )
}

export function facultyMlAvailableCount(
  models: Record<FacultyMlModelKey, FacultyMlModelInsight>
): number {
  return Object.values(models).filter((model) => model.available).length
}

export function facultyMlBandTone(
  band: string | null | undefined
): "success" | "secondary" | "warning" | "destructive" {
  if (band === "Top Performer" || band === "Above Average") return "success"
  if (band === "Average") return "secondary"
  if (band === "Below Average") return "warning"
  return "destructive"
}

export function facultyMlReadinessTone(level: string): "success" | "warning" | "destructive" {
  if (level.toLowerCase() === "high") return "success"
  if (level.toLowerCase() === "medium") return "warning"
  return "destructive"
}

export function getFacultySubjects(params?: {
  semester?: string | number | null
  academic_year?: string | null
  batch?: string | null
  search?: string | null
  page?: number
  page_size?: number
  sort?: string
  order?: "asc" | "desc"
  all_terms?: boolean
}): Promise<BffResult<FacultySubjectsResponse>> {
  const searchParams = new URLSearchParams()
  if (params?.semester !== undefined) searchParams.set("semester", String(params.semester))
  if (params?.academic_year !== undefined)
    searchParams.set("academic_year", params.academic_year ?? "")
  if (params?.batch !== undefined && params.batch !== null)
    searchParams.set("batch", params.batch ?? "all")
  if (params?.search) searchParams.set("search", params.search)
  if (params?.page) searchParams.set("page", params.page.toString())
  if (params?.page_size) searchParams.set("page_size", params.page_size.toString())
  if (params?.sort) searchParams.set("sort", params.sort)
  if (params?.order) searchParams.set("order", params.order)
  if (params?.all_terms) searchParams.set("all_terms", "true")

  const query = searchParams.toString()
  const path = query ? `subjects?${query}` : "subjects"
  return callFastapi<FacultySubjectsResponse>(path, BFF_TTL_MS)
}

export function getFacultySubjectDetail(
  subjectId: string,
  params?: {
    semester?: number | null
    academic_year?: string | null
  }
): Promise<BffResult<FacultySubjectDetail>> {
  const searchParams = new URLSearchParams()
  if (params?.semester) searchParams.set("semester", params.semester.toString())
  if (params?.academic_year) searchParams.set("academic_year", params.academic_year)

  const query = searchParams.toString()
  const path = query ? `subjects/${subjectId}?${query}` : `subjects/${subjectId}`
  return callFastapi<FacultySubjectDetail>(path, BFF_TTL_MS)
}

export function getFacultySubjectHistory(
  subjectId: string
): Promise<BffResult<FacultySubjectHistory>> {
  return callFastapi<FacultySubjectHistory>(`subjects/${subjectId}/history`, BFF_TTL_MS)
}

export type PerformanceAppliedFilters = {
  semester: number | null
  academic_year: string | null
  subject_id: string | null
  compare: boolean
}

export type PerformanceKpi = {
  key: string
  label: string
  value: number | null
  display: string
  delta: number | null
  previous_display: string | null
  has_previous: boolean
}

export type PerformanceFilters = {
  semesters: number[]
  academic_years: string[]
  subjects: FacultySubjectOption[]
  term_options: FacultyTermOption[]
}

export type PerformanceThresholds = {
  performance: number
  attendance: number
  critical_performance: number
  pass_rate_watch: number
  pass_rate_healthy: number
  distinction_grade_point: number
}

export type PerformanceSummary = {
  faculty_id: string
  kpis: PerformanceKpi[]
  filters: PerformanceFilters
  applied: PerformanceAppliedFilters
  current_term: FacultyTermOption | null
  previous_term: FacultyTermOption | null
  thresholds: PerformanceThresholds
}

export type DistributionItem = {
  label: string
  count: number
}

export type AttemptItem = {
  attempt: string
  pass_count: number
  fail_count: number
}

export type PerformanceDistributions = {
  grade_distribution: FacultySubjectGradeItem[]
  performance_bands: DistributionItem[]
  attendance_bands: DistributionItem[]
  attempt_analysis: AttemptItem[]
  category_distribution: DistributionItem[]
}

export type SubjectBreakdownItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  enrollments: number
  average_performance: number | null
  average_attendance: number | null
  pass_percentage: number | null
}

export type PerformanceSubjectBreakdown = {
  items: SubjectBreakdownItem[]
}

export type PerformanceTrendItem = {
  label: string
  semester_no: number
  academic_year: string
  average_performance: number | null
  average_attendance: number | null
  pass_percentage: number | null
}

export type PerformanceTrends = {
  items: PerformanceTrendItem[]
}

export type LearningGapItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  status: "Critical" | "Watch" | "Healthy"
  average_performance: number | null
  average_attendance: number | null
  pass_percentage: number | null
  reason: string | null
  delta: number | null
  below_baseline_count: number
  ineligible_count: number
}

export type PerformanceLearningGaps = {
  items: LearningGapItem[]
  critical_count: number
  watch_count: number
  healthy_count: number
}

export type PerformanceStudentRow = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  semester_no: number
  subject_id: string
  subject_code: string
  subject_name: string
  first_name: string
  last_name: string
  attendance_percentage: number | null
  total_marks: number | null
  grade: string | null
  result_status: string | null
  gap_status: string
}

export type PerformanceStudentsResponse = {
  faculty_id: string
  applied: PerformanceAppliedFilters
  rows: PerformanceStudentRow[]
  pagination: FacultyPagination
}

export type PerformanceInsight = {
  id: string
  severity: "info" | "warning" | "critical"
  message: string
  subject_id: string | null
  subject_code: string | null
  term_label: string | null
}

export type PerformanceInsightsResponse = {
  items: PerformanceInsight[]
}

export type AttendanceFilters = {
  semesters: number[]
  academic_years: string[]
  subjects: FacultySubjectOption[]
  term_options: FacultyTermOption[]
  attendance_ranges: string[]
  attendance_statuses: string[]
  defaulter_statuses: string[]
  student_statuses: string[]
}

export type AttendanceAppliedFilters = {
  semester: number | null
  academic_year: string | null
  subject_id: string | null
  compare: boolean
  attendance_range: string | null
  attendance_status: string | null
  defaulter_status: string | null
  student_status: string | null
}

export type AttendanceThresholds = {
  compliance: number
  critical: number
  excellent: number
}

export type AttendanceSummary = {
  faculty_id: string
  kpis: PerformanceKpi[]
  filters: AttendanceFilters
  applied: AttendanceAppliedFilters
  current_term: FacultyTermOption | null
  previous_term: FacultyTermOption | null
  thresholds: AttendanceThresholds
}

export type AttendanceHeatmapCell = {
  student_id: string
  subject_id: string
  subject_code: string
  first_name: string
  last_name: string
  attendance_percentage: number | null
}

export type AttendanceDistributions = {
  status_distribution: DistributionItem[]
  attendance_bands: DistributionItem[]
  heatmap: AttendanceHeatmapCell[]
  above_below: DistributionItem[]
}

export type AttendanceSubjectItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  enrollments: number
  average_attendance: number | null
  above_threshold: number
  below_threshold: number
  compliance_percentage: number | null
  health_band: string
  reason: string | null
  previous_average_attendance: number | null
  previous_academic_year: string | null
}

export type AttendanceSubjectBreakdown = {
  items: AttendanceSubjectItem[]
}

export type AttendanceTrendItem = {
  label: string
  semester_no: number
  academic_year: string
  average_attendance: number | null
}

export type AttendanceTrendBySubjectItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  average_attendance: number | null
}

export type AttendanceTrends = {
  items: AttendanceTrendItem[]
  by_subject: AttendanceTrendBySubjectItem[]
}

export type AttendanceGovernanceItem = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  semester_no: number
  subject_id: string
  subject_code: string
  subject_name: string
  first_name: string
  last_name: string
  attendance_percentage: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
  band: "Critical" | "Watch" | "Healthy"
  reason: string
  delta: number | null
  previous_display: string | null
  previous_reason: string | null
  total_classes: number | null
  attended_classes: number | null
}

export type AttendanceGovernance = {
  items: AttendanceGovernanceItem[]
  critical_count: number
  watch_count: number
  healthy_count: number
  band: string | null
}

export type AttendanceHealthScoreItem = {
  subject_id: string | null
  subject_code: string | null
  subject_name: string | null
  student_id: string | null
  enrollment_no: number | null
  student_name: string | null
  band: string
  reason: string
  attendance_percentage: number | null
}

export type AttendanceHealthScore = {
  scope_band: string
  scope_reason: string
  subjects: AttendanceHealthScoreItem[]
  students: AttendanceHealthScoreItem[]
}

export type AttendanceStudentRow = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  semester_no: number
  subject_id: string
  subject_code: string
  subject_name: string
  first_name: string
  last_name: string
  attendance_percentage: number | null
  attended_classes: number | null
  total_classes: number | null
  attendance_status: string | null
  eligibility_status: string | null
  defaulter_status: "Defaulter" | "Non-Defaulter"
  band: "Critical" | "Watch" | "Healthy"
  reason: string
}

export type AttendanceStudentsResponse = {
  faculty_id: string
  applied: AttendanceAppliedFilters
  rows: AttendanceStudentRow[]
  pagination: FacultyPagination
}

export type AttendanceHighlight = {
  id: string
  severity: "info" | "warning" | "critical"
  message: string
  subject_id: string | null
  subject_code: string | null
  term_label: string | null
}

export type AttendanceHighlightsResponse = {
  items: AttendanceHighlight[]
}

export type AttendanceCorrelationPoint = {
  attendance_percentage: number | null
  performance_percentage: number | null
}

export type AttendanceCorrelation = {
  points: AttendanceCorrelationPoint[]
  pearson: number | null
  descriptor: string | null
  sample_size: number
}

export type AttendanceSummaryParams = {
  semester?: number | null
  academic_year?: string | null
  subject_id?: string | null
  compare?: boolean
}

export type AttendanceStudentsParams = AttendanceSummaryParams & {
  page?: number
  page_size?: number
  search?: string | null
  attendance_range?: string | null
  attendance_status?: string | null
  defaulter_status?: string | null
  student_status?: string | null
  sort?: string
  order?: "asc" | "desc"
}

export type AttendanceGovernanceParams = AttendanceSummaryParams & {
  band?: string | null
}

export type AttendanceExportParams = AttendanceSummaryParams & {
  search?: string | null
  student_ids?: string[]
}

export type PerformanceSummaryParams = {
  semester?: number | null
  academic_year?: string | null
  subject_id?: string | null
  compare?: boolean
}

export type PerformanceStudentsParams = PerformanceSummaryParams & {
  page?: number
  page_size?: number
  search?: string | null
  gap_status?: string | null
  sort?: string
  order?: "asc" | "desc"
}

export type PerformanceExportParams = PerformanceSummaryParams & {
  search?: string | null
  student_ids?: string[]
}

function performanceScopeQuery(params: PerformanceStudentsParams): string {
  const searchParams = new URLSearchParams()
  if (params.semester !== undefined && params.semester !== null) {
    searchParams.set("semester", String(params.semester))
  }
  if (params.academic_year) searchParams.set("academic_year", params.academic_year)
  if (params.subject_id) searchParams.set("subject_id", params.subject_id)
  if (params.compare) searchParams.set("compare", "true")
  if (params.page !== undefined && params.page !== null) {
    searchParams.set("page", String(params.page))
  }
  if (params.page_size !== undefined && params.page_size !== null) {
    searchParams.set("page_size", String(params.page_size))
  }
  if (params.search) searchParams.set("search", params.search)
  if (params.gap_status) searchParams.set("gap_status", params.gap_status)
  if (params.sort) searchParams.set("sort", params.sort)
  if (params.order) searchParams.set("order", params.order)
  return searchParams.toString()
}

export function getFacultyPerformanceSummary(
  params?: PerformanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceSummary>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/summary?${query}` : "performance/summary"
  return callFastapi<PerformanceSummary>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getFacultyPerformanceDistributions(
  params?: PerformanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceDistributions>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/distributions?${query}` : "performance/distributions"
  return callFastapi<PerformanceDistributions>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getFacultyPerformanceSubjectBreakdown(
  params?: PerformanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceSubjectBreakdown>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/subject-breakdown?${query}` : "performance/subject-breakdown"
  return callFastapi<PerformanceSubjectBreakdown>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getFacultyPerformanceTrends(
  params?: PerformanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceTrends>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/trends?${query}` : "performance/trends"
  return callFastapi<PerformanceTrends>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getFacultyPerformanceLearningGaps(
  params?: PerformanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceLearningGaps>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/learning-gaps?${query}` : "performance/learning-gaps"
  return callFastapi<PerformanceLearningGaps>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getFacultyPerformanceStudents(
  params?: PerformanceStudentsParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceStudentsResponse>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/students?${query}` : "performance/students"
  return callFastapi<PerformanceStudentsResponse>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getFacultyPerformanceInsights(
  params?: PerformanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<PerformanceInsightsResponse>> {
  const query = performanceScopeQuery(params ?? {})
  const path = query ? `performance/insights?${query}` : "performance/insights"
  return callFastapi<PerformanceInsightsResponse>(path, BFF_TTL_MS, opts?.bypassCache)
}

export async function getFacultyPerformanceExport(
  params?: PerformanceExportParams,
): Promise<BffResult<string>> {
  const user = await getSessionUser()
  if (!user) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to export this data.",
      },
    }
  }
  if (user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to export faculty data.",
      },
    }
  }

  const searchParams = new URLSearchParams()
  if (params?.semester !== undefined && params?.semester !== null) {
    searchParams.set("semester", String(params.semester))
  }
  if (params?.academic_year) searchParams.set("academic_year", params.academic_year)
  if (params?.subject_id) searchParams.set("subject_id", params.subject_id)
  if (params?.search) searchParams.set("search", params.search)
  if (params?.student_ids?.length) {
    searchParams.set("student_ids", params.student_ids.join(","))
  }
  const query = searchParams.toString()
  const path = query
    ? `/api/v1/faculty/performance/export?${query}`
    : "/api/v1/faculty/performance/export"

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
    if (!res.ok) {
      return { ok: false, error: toBffError(res.status) }
    }
    const text = await res.text()
    return { ok: true, data: text, fetchedAt: new Date().toISOString() }
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

function attendanceScopeQuery(params: {
  semester?: number | null
  academic_year?: string | null
  subject_id?: string | null
  compare?: boolean
  page?: number
  page_size?: number
  search?: string | null
  attendance_range?: string | null
  attendance_status?: string | null
  defaulter_status?: string | null
  student_status?: string | null
  band?: string | null
  sort?: string
  order?: "asc" | "desc"
}): string {
  const searchParams = new URLSearchParams()
  if (params.semester !== undefined && params.semester !== null) {
    searchParams.set("semester", String(params.semester))
  }
  if (params.academic_year) {
    searchParams.set("academic_year", params.academic_year)
  }
  if (params.subject_id) {
    searchParams.set("subject_id", params.subject_id)
  }
  if (params.compare) {
    searchParams.set("compare", "true")
  }
  if (params.page !== undefined && params.page !== null) {
    searchParams.set("page", String(params.page))
  }
  if (params.page_size !== undefined && params.page_size !== null) {
    searchParams.set("page_size", String(params.page_size))
  }
  if (params.search) {
    searchParams.set("search", params.search)
  }
  if (params.attendance_range) {
    searchParams.set("attendance_range", params.attendance_range)
  }
  if (params.attendance_status) {
    searchParams.set("attendance_status", params.attendance_status)
  }
  if (params.defaulter_status) {
    searchParams.set("defaulter_status", params.defaulter_status)
  }
  if (params.student_status) {
    searchParams.set("student_status", params.student_status)
  }
  if (params.band) {
    searchParams.set("band", params.band)
  }
  if (params.sort) {
    searchParams.set("sort", params.sort)
  }
  if (params.order) {
    searchParams.set("order", params.order)
  }
  return searchParams.toString()
}

function attendancePath(segment: string, query: string): string {
  return query ? `attendance/${segment}?${query}` : `attendance/${segment}`
}

export function getFacultyAttendanceSummary(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceSummary>> {
  return callFastapi<AttendanceSummary>(
    attendancePath("summary", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceDistributions(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceDistributions>> {
  return callFastapi<AttendanceDistributions>(
    attendancePath("distributions", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceSubjectBreakdown(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceSubjectBreakdown>> {
  return callFastapi<AttendanceSubjectBreakdown>(
    attendancePath("subject-breakdown", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceTrends(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceTrends>> {
  return callFastapi<AttendanceTrends>(
    attendancePath("trends", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceGovernance(
  params?: AttendanceGovernanceParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceGovernance>> {
  return callFastapi<AttendanceGovernance>(
    attendancePath("governance", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceHealthScore(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceHealthScore>> {
  return callFastapi<AttendanceHealthScore>(
    attendancePath("health-score", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceStudents(
  params?: AttendanceStudentsParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceStudentsResponse>> {
  return callFastapi<AttendanceStudentsResponse>(
    attendancePath("students", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceHighlights(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceHighlightsResponse>> {
  return callFastapi<AttendanceHighlightsResponse>(
    attendancePath("highlights", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyAttendanceCorrelation(
  params?: AttendanceSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceCorrelation>> {
  return callFastapi<AttendanceCorrelation>(
    attendancePath("correlation", attendanceScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export async function getFacultyAttendanceExport(
  params?: AttendanceExportParams,
): Promise<BffResult<string>> {
  const user = await getSessionUser()
  if (!user) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to export this data.",
      },
    }
  }
  if (user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to export faculty data.",
      },
    }
  }

  const searchParams = new URLSearchParams()
  if (params?.semester !== undefined && params?.semester !== null) {
    searchParams.set("semester", String(params.semester))
  }
  if (params?.academic_year) {
    searchParams.set("academic_year", params.academic_year)
  }
  if (params?.subject_id) {
    searchParams.set("subject_id", params.subject_id)
  }
  if (params?.search) {
    searchParams.set("search", params.search)
  }
  if (params?.student_ids?.length) {
    searchParams.set("student_ids", params.student_ids.join(","))
  }
  const query = searchParams.toString()
  const path = query
    ? `/api/v1/faculty/attendance/export?${query}`
    : "/api/v1/faculty/attendance/export"

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
    if (!res.ok) {
      return { ok: false, error: toBffError(res.status) }
    }
    const text = await res.text()
    return { ok: true, data: text, fetchedAt: new Date().toISOString() }
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

export type WorkloadFilters = {
  semesters: number[]
  academic_years: string[]
  subjects: FacultySubjectOption[]
  term_options: FacultyTermOption[]
  subject_types: string[]
  workload_statuses: string[]
}

export type WorkloadAppliedFilters = {
  semester: number | null
  academic_year: string | null
  subject_id: string | null
  compare: boolean
}

export type WorkloadThresholds = {
  capacity_weekly_hours: number
  weeks_per_semester: number
  overload_threshold: number
  underutilized_threshold: number
  balance_watch: number
  coverage_watch: number
  credit_imbalance_ratio: number
  student_imbalance_ratio: number
  health_excellent: number
  health_good: number
  health_watch: number
  health_critical: number
}

export type WorkloadHealthItem = {
  score: number | null
  band: string
  reason: string
}

export type WorkloadSummary = {
  faculty_id: string
  kpis: PerformanceKpi[]
  filters: WorkloadFilters
  applied: WorkloadAppliedFilters
  current_term: FacultyTermOption | null
  previous_term: FacultyTermOption | null
  thresholds: WorkloadThresholds
  health: WorkloadHealthItem
}

export type WorkloadSubjectItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  subject_type: string | null
  credits: number | null
  students: number
  classes: number | null
  weekly_hours: number | null
}

export type WorkloadTypeItem = {
  label: string
  count: number
  credits: number | null
}

export type WorkloadBalanceMatrixCell = {
  subject_id: string
  subject_code: string
  metric: string
  value: number
  normalized: number
  band?: string | null
}

export type WorkloadSubjectBreakdown = {
  items: WorkloadSubjectItem[]
  type_distribution: WorkloadTypeItem[]
  theory_practical: WorkloadTypeItem[]
  balance_matrix: WorkloadBalanceMatrixCell[]
}

export type WorkloadTrendItem = {
  label: string
  semester_no: number
  academic_year: string
  subjects: number
  credits: number
  students: number
  classes: number | null
  weekly_hours: number
}

export type WorkloadTrendBySubjectItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  weekly_hours: number | null
}

export type WorkloadCapacityTrendItem = {
  label: string
  semester_no: number
  academic_year: string
  weekly_hours: number
  capacity: number
}

export type WorkloadTrends = {
  items: WorkloadTrendItem[]
  by_subject: WorkloadTrendBySubjectItem[]
  capacity_trend: WorkloadCapacityTrendItem[]
}

export type WorkloadCapacity = {
  actual_weekly_hours: number
  capacity_weekly_hours: number
  utilization_pct: number
  remaining_capacity: number
  band: string
  reason: string
}

export type WorkloadMatrixCell = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  metric: string
  label: string
  value: number
  normalized: number
  band?: string | null
}

export type WorkloadMatrices = {
  heatmap: WorkloadMatrixCell[]
  utilization: WorkloadMatrixCell[]
  allocation: WorkloadMatrixCell[]
}

export type WorkloadScatterPoint = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  students: number
  credits: number | null
}

export type WorkloadScatter = {
  points: WorkloadScatterPoint[]
}

export type DepartmentResourceSummary = {
  faculty_count: number
  total_offerings: number
  total_students: number
  total_credits: number
  total_classes: number | null
  mean_weekly_hours: number | null
  mean_capacity_utilization: number | null
}

export type WorkloadBenchmarkItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  weekly_hours: number | null
}

export type WorkloadBenchmark = {
  items: WorkloadBenchmarkItem[]
  department_mean_weekly_hours: number | null
  department_summary: DepartmentResourceSummary
}

export type WorkloadForecastItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  expected_weekly_hours: number | null
  prior_offerings: number
  source_reason: string
}

export type WorkloadForecast = {
  items: WorkloadForecastItem[]
  expected_total_weekly_hours: number | null
  remaining_capacity: number | null
  source_reason: string
}

export type WorkloadGovernanceItem = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  status: string
  credits: number
  students: number
  teaching_hours: number | null
  reason: string
  delta: number | null
  previous_display: string | null
  previous_reason: string | null
}

export type WorkloadGovernance = {
  items: WorkloadGovernanceItem[]
  overloaded_count: number
  balanced_count: number
  underutilized_count: number
  no_data_count: number
  credit_imbalance_count: number
  student_imbalance_count: number
  capacity_warning_count: number
}

export type WorkloadHealthScoreItem = {
  subject_id: string | null
  subject_code: string | null
  subject_name: string | null
  score: number | null
  band: string
  reason: string
}

export type WorkloadHealthScore = {
  scope_score: number | null
  scope_band: string
  scope_reason: string
  subjects: WorkloadHealthScoreItem[]
}

export type WorkloadTimelineItem = {
  label: string
  semester_no: number
  academic_year: string
  subjects: number
  credits: number | null
  students: number | null
  classes: number | null
  weekly_hours: number
  delta_credits: number | null
  delta_hours: number | null
  delta_students: number | null
  projected: boolean
  source_reason: string | null
}

export type WorkloadTimeline = {
  items: WorkloadTimelineItem[]
}

export type WorkloadStudentRow = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  semester_no: number
  subject_id: string
  subject_code: string
  subject_name: string
  first_name: string
  last_name: string
  credits: number | null
  weekly_hours: number | null
  classes_conducted: number | null
  workload_status: string
}

export type WorkloadStudentsResponse = {
  faculty_id: string
  applied: WorkloadAppliedFilters
  rows: WorkloadStudentRow[]
  pagination: FacultyPagination
}

export type WorkloadHighlight = {
  id: string
  severity: "info" | "warning"
  message: string
  subject_id: string | null
  subject_code: string | null
  term_label: string | null
}

export type WorkloadHighlightsResponse = {
  items: WorkloadHighlight[]
}

export type WorkloadSummaryParams = {
  semester?: number | null
  academic_year?: string | null
  subject_id?: string | null
  compare?: boolean
}

export type WorkloadStudentsParams = WorkloadSummaryParams & {
  subject_type?: string | null
  credits_min?: number | null
  credits_max?: number | null
  hours_min?: number | null
  hours_max?: number | null
  students_min?: number | null
  students_max?: number | null
  search?: string | null
  workload_status?: string | null
  page?: number
  page_size?: number
  sort?: string
  order?: "asc" | "desc"
}

export type WorkloadGovernanceParams = WorkloadSummaryParams & {
  status?: string | null
}

export type WorkloadExportParams = WorkloadSummaryParams & {
  report?: string
  subject_type?: string | null
  credits_min?: number | null
  credits_max?: number | null
  hours_min?: number | null
  hours_max?: number | null
  students_min?: number | null
  students_max?: number | null
  workload_status?: string | null
  search?: string | null
  student_ids?: string[]
}

function workloadScopeQuery(params: {
  semester?: number | null
  academic_year?: string | null
  subject_id?: string | null
  compare?: boolean
  subject_type?: string | null
  credits_min?: number | null
  credits_max?: number | null
  hours_min?: number | null
  hours_max?: number | null
  students_min?: number | null
  students_max?: number | null
  search?: string | null
  workload_status?: string | null
  page?: number
  page_size?: number
  sort?: string
  order?: "asc" | "desc"
}): string {
  const searchParams = new URLSearchParams()
  if (params.semester !== undefined && params.semester !== null) {
    searchParams.set("semester", String(params.semester))
  }
  if (params.academic_year) {
    searchParams.set("academic_year", params.academic_year)
  }
  if (params.subject_id) {
    searchParams.set("subject_id", params.subject_id)
  }
  if (params.compare) {
    searchParams.set("compare", "true")
  }
  if (params.subject_type) {
    searchParams.set("subject_type", params.subject_type)
  }
  if (params.credits_min !== undefined && params.credits_min !== null) {
    searchParams.set("credits_min", String(params.credits_min))
  }
  if (params.credits_max !== undefined && params.credits_max !== null) {
    searchParams.set("credits_max", String(params.credits_max))
  }
  if (params.hours_min !== undefined && params.hours_min !== null) {
    searchParams.set("hours_min", String(params.hours_min))
  }
  if (params.hours_max !== undefined && params.hours_max !== null) {
    searchParams.set("hours_max", String(params.hours_max))
  }
  if (params.students_min !== undefined && params.students_min !== null) {
    searchParams.set("students_min", String(params.students_min))
  }
  if (params.students_max !== undefined && params.students_max !== null) {
    searchParams.set("students_max", String(params.students_max))
  }
  if (params.search) {
    searchParams.set("search", params.search)
  }
  if (params.workload_status) {
    searchParams.set("workload_status", params.workload_status)
  }
  if (params.page !== undefined && params.page !== null) {
    searchParams.set("page", String(params.page))
  }
  if (params.page_size !== undefined && params.page_size !== null) {
    searchParams.set("page_size", String(params.page_size))
  }
  if (params.sort) {
    searchParams.set("sort", params.sort)
  }
  if (params.order) {
    searchParams.set("order", params.order)
  }
  return searchParams.toString()
}

function workloadPath(segment: string, query: string): string {
  return query ? `workload/${segment}?${query}` : `workload/${segment}`
}

export function getFacultyWorkloadSummary(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadSummary>> {
  return callFastapi<WorkloadSummary>(
    workloadPath("summary", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadSubjectBreakdown(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadSubjectBreakdown>> {
  return callFastapi<WorkloadSubjectBreakdown>(
    workloadPath("subject-breakdown", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadTrends(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadTrends>> {
  return callFastapi<WorkloadTrends>(
    workloadPath("trends", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadCapacity(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadCapacity>> {
  return callFastapi<WorkloadCapacity>(
    workloadPath("capacity", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadMatrices(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadMatrices>> {
  return callFastapi<WorkloadMatrices>(
    workloadPath("matrices", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadScatter(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadScatter>> {
  return callFastapi<WorkloadScatter>(
    workloadPath("scatter", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadBenchmark(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadBenchmark>> {
  return callFastapi<WorkloadBenchmark>(
    workloadPath("benchmark", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadForecast(
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadForecast>> {
  return callFastapi<WorkloadForecast>(
    workloadPath("forecast", ""),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadGovernance(
  params?: WorkloadGovernanceParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadGovernance>> {
  return callFastapi<WorkloadGovernance>(
    workloadPath("governance", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadHealthScore(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadHealthScore>> {
  return callFastapi<WorkloadHealthScore>(
    workloadPath("health-score", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadTimeline(
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadTimeline>> {
  return callFastapi<WorkloadTimeline>(
    workloadPath("timeline", ""),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadStudents(
  params?: WorkloadStudentsParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadStudentsResponse>> {
  return callFastapi<WorkloadStudentsResponse>(
    workloadPath("students", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function getFacultyWorkloadHighlights(
  params?: WorkloadSummaryParams,
  opts?: { bypassCache?: boolean },
): Promise<BffResult<WorkloadHighlightsResponse>> {
  return callFastapi<WorkloadHighlightsResponse>(
    workloadPath("highlights", workloadScopeQuery(params ?? {})),
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export async function getFacultyWorkloadExport(
  params?: WorkloadExportParams,
): Promise<BffResult<string>> {
  const user = await getSessionUser()
  if (!user) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to export this data.",
      },
    }
  }
  if (user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 403,
        code: "unauthorized",
        message: "This account is not allowed to export faculty data.",
      },
    }
  }

  const searchParams = new URLSearchParams()
  if (params?.report) {
    searchParams.set("report", params.report)
  }
  if (params?.semester !== undefined && params?.semester !== null) {
    searchParams.set("semester", String(params.semester))
  }
  if (params?.academic_year) {
    searchParams.set("academic_year", params.academic_year)
  }
  if (params?.subject_id) {
    searchParams.set("subject_id", params.subject_id)
  }
  if (params?.subject_type) {
    searchParams.set("subject_type", params.subject_type)
  }
  if (params?.credits_min !== undefined && params?.credits_min !== null) {
    searchParams.set("credits_min", String(params.credits_min))
  }
  if (params?.credits_max !== undefined && params?.credits_max !== null) {
    searchParams.set("credits_max", String(params.credits_max))
  }
  if (params?.hours_min !== undefined && params?.hours_min !== null) {
    searchParams.set("hours_min", String(params.hours_min))
  }
  if (params?.hours_max !== undefined && params?.hours_max !== null) {
    searchParams.set("hours_max", String(params.hours_max))
  }
  if (params?.students_min !== undefined && params?.students_min !== null) {
    searchParams.set("students_min", String(params.students_min))
  }
  if (params?.students_max !== undefined && params?.students_max !== null) {
    searchParams.set("students_max", String(params.students_max))
  }
  if (params?.workload_status) {
    searchParams.set("workload_status", params.workload_status)
  }
  if (params?.search) {
    searchParams.set("search", params.search)
  }
  if (params?.student_ids?.length) {
    searchParams.set("student_ids", params.student_ids.join(","))
  }
  const query = searchParams.toString()
  const path = query
    ? `/api/v1/faculty/workload/export?${query}`
    : "/api/v1/faculty/workload/export"

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
    if (!res.ok) {
      return { ok: false, error: toBffError(res.status) }
    }
    const text = await res.text()
    return { ok: true, data: text, fetchedAt: new Date().toISOString() }
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

export type SettingsActivityEntry = {
  event: string
  at: string
  namespace?: string | null
  detail?: string | null
}

export type PreferenceMetadata = {
  schema_version: number
  preference_version: number
  configuration_version: number
  last_modified?: string | null
  last_synced?: string | null
  restore_point?: Record<string, unknown> | null
}

export type FacultySettingsNamespaces = {
  workspace: Record<string, unknown>
  dashboard: Record<string, unknown>
  analytics: Record<string, unknown>
  notifications: Record<string, unknown>
  export: Record<string, unknown>
  accessibility: Record<string, unknown>
  personalization: Record<string, unknown>
  security: Record<string, unknown>
  profile_extra: Record<string, unknown>
}

export type FacultySettingsResponse = {
  namespaces: FacultySettingsNamespaces
  metadata: PreferenceMetadata
  activity: SettingsActivityEntry[]
}

export type FacultySettingsUpdateResponse = FacultySettingsResponse & {
  highlights: string[]
}

export function getFacultySettings(): Promise<BffResult<FacultySettingsResponse>> {
  return callFastapi<FacultySettingsResponse>("settings", BFF_TTL_MS)
}

export async function updateFacultySettings(
  namespace: string,
  patch: Record<string, unknown>,
): Promise<BffResult<FacultySettingsUpdateResponse>> {
  const user = await getSessionUser()
  if (!user || user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to update your settings.",
      },
    }
  }

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/faculty/settings/${namespace}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(patch),
      cache: "no-store",
    })
    if (!res.ok) {
      if (res.status === 400) {
        const body = await res.json().catch(() => null)
        return {
          ok: false,
          error: {
            status: 400,
            code: "invalid",
            message:
              typeof body?.detail === "string" ? body.detail : "That preference is not valid.",
          },
        }
      }
      return { ok: false, error: toBffError(res.status) }
    }
    const data = (await res.json()) as FacultySettingsUpdateResponse
    bffCache.delete(`${user.faculty_id}:settings`)
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

export type SettingsResetLevel =
  | "dashboard"
  | "analytics"
  | "notifications"
  | "accessibility"
  | "workspace"
  | "factory"

export type FacultySettingsBackup = {
  schema_version: number
  preference_version: number
  configuration_version: number
  exported_at: string
  namespaces: Record<string, unknown>
}

async function postFacultySettingsAction<T>(
  path: string,
  body: Record<string, unknown> | null,
): Promise<BffResult<T>> {
  const user = await getSessionUser()
  if (!user || user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to update your settings.",
      },
    }
  }

  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/faculty/${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    })
    if (!res.ok) {
      if (res.status === 400) {
        const errorBody = await res.json().catch(() => null)
        return {
          ok: false,
          error: {
            status: 400,
            code: "invalid",
            message:
              typeof errorBody?.detail === "string"
                ? errorBody.detail
                : "That action could not be completed.",
          },
        }
      }
      return { ok: false, error: toBffError(res.status) }
    }
    const data = (await res.json()) as T
    bffCache.delete(`${user.faculty_id}:settings`)
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

export function getFacultySettingsBackup(): Promise<BffResult<FacultySettingsBackup>> {
  return callFastapi<FacultySettingsBackup>("settings/workspace/backup", BFF_TTL_MS)
}

export function resetFacultySettings(
  level: SettingsResetLevel,
  includeProfileExtra = false,
): Promise<BffResult<FacultySettingsUpdateResponse>> {
  return postFacultySettingsAction<FacultySettingsUpdateResponse>("settings/reset", {
    level,
    include_profile_extra: includeProfileExtra,
  })
}

export function importFacultySettings(
  payload: Record<string, unknown>,
): Promise<BffResult<FacultySettingsUpdateResponse>> {
  return postFacultySettingsAction<FacultySettingsUpdateResponse>("settings/workspace/import", {
    payload,
  })
}

export function restoreFacultySettings(): Promise<BffResult<FacultySettingsUpdateResponse>> {
  return postFacultySettingsAction<FacultySettingsUpdateResponse>("settings/workspace/restore", null)
}

// =============================================================================
// Marks Entry (plan 14) + Attendance Entry (plan 15) — BFF layer
// =============================================================================

function invalidateBffKeys(facultyId: string, prefixes: string[]) {
  const base = `${facultyId}:`
  for (const key of Array.from(bffCache.keys())) {
    if (prefixes.some((p) => key.startsWith(`${base}${p}`))) {
      bffCache.delete(key)
    }
  }
}

async function mutateFastapi<T>(
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  body: unknown,
  invalidatePrefixes: string[],
): Promise<BffResult<T>> {
  const user = await getSessionUser()
  if (!user || user.role !== "Faculty" || !user.faculty_id) {
    return {
      ok: false,
      error: {
        status: 401,
        code: "unauthorized",
        message: "You must be signed in to make changes.",
      },
    }
  }
  try {
    const token = Buffer.from(JSON.stringify(user), "utf-8").toString("base64")
    const res = await fetch(`${FASTAPI_URL}/api/v1/faculty/${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    if (!res.ok) {
      let customDetail: string | undefined
      try {
        const errBody = await res.json()
        if (typeof errBody?.detail === "string" && errBody.detail.trim()) {
          customDetail = errBody.detail
        } else if (typeof errBody?.message === "string" && errBody.message.trim()) {
          customDetail = errBody.message
        }
      } catch {}
      return { ok: false, error: toBffError(res.status, customDetail) }
    }
    const data = (await res.json()) as T
    invalidateBffKeys(user.faculty_id, invalidatePrefixes)
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

export type MarksBand = { min_percentage: number; grade: string; grade_point: number }

export type MarksCategoryBand = { min_percentage: number; category: string }

export type MarksRemarkBand = { min_percentage: number; remark: string }

export type MarksConfig = {
  internal_max: number
  mid_sem_max: number
  end_sem_max: number
  total_max: number
  pass_percentage: number
  end_sem_pass_min: number
  remarks_max_length: number
  grade_bands: MarksBand[]
  category_bands: MarksCategoryBand[]
  remark_bands: MarksRemarkBand[]
}

export type SubjectMarksRow = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  first_name: string
  last_name: string
  internal_marks: number | null
  mid_sem_marks: number | null
  end_sem_marks: number | null
  total_marks: number | null
  percentage: number | null
  grade: string | null
  grade_point: number | null
  result_status: string | null
  performance_category: string | null
  remarks: string | null
  complete: boolean
}

export type SubjectMarksGrid = {
  subject_id: string
  subject_code: string
  subject_name: string
  credits: number | null
  semester_no: number
  academic_year: string
  assessment_type: string | null
  department_name: string | null
  config: MarksConfig
  rows: SubjectMarksRow[]
  pagination: FacultyPagination
}

export type MarksRowInput = {
  enrollment_record_id: string
  internal_marks?: number | null
  mid_sem_marks?: number | null
  end_sem_marks?: number | null
}

export type MarksBatchSaveRequest = {
  semester_no: number
  academic_year: string
  rows: MarksRowInput[]
}

export type MarksSaveResult = {
  enrollment_record_id: string
  student_id: string
  operation: string
  fields_changed: string[]
}

export type MarksSaveSummary = {
  saved: number
  inserted: number
  updated: number
  unchanged: number
  rejected: number
}

export type MarksBatchSaveResponse = {
  subject_id: string
  semester_no: number
  academic_year: string
  summary: MarksSaveSummary
  rows: MarksSaveResult[]
  grid: SubjectMarksGrid
}

export type MarksChangeLogItem = {
  change_id: number
  performance_id: string
  enrollment_record_id: string
  student_id: string
  student_name: string | null
  subject_id: string
  field_name: string
  old_value: unknown
  new_value: unknown
  operation_type: string
  changed_by: string | null
  changed_at: string
}

export type MarksChangeLogResponse = {
  subject_id: string
  semester_no: number
  academic_year: string
  items: MarksChangeLogItem[]
  pagination: FacultyPagination
}

export type MarksQueryParams = {
  semester?: number | null
  academic_year?: string | null
  page?: number
  page_size?: number
  sort?: string
  order?: "asc" | "desc"
}

export function getSubjectMarks(
  subjectId: string,
  params: MarksQueryParams = {},
  opts?: { bypassCache?: boolean },
): Promise<BffResult<SubjectMarksGrid>> {
  const searchParams = new URLSearchParams()
  if (params.semester !== undefined) searchParams.set("semester", String(params.semester))
  if (params.academic_year !== undefined)
    searchParams.set("academic_year", params.academic_year ?? "")
  if (params.page) searchParams.set("page", String(params.page))
  if (params.page_size) searchParams.set("page_size", String(params.page_size))
  if (params.sort) searchParams.set("sort", params.sort)
  if (params.order) searchParams.set("order", params.order)
  const query = searchParams.toString()
  const path = query ? `subjects/${subjectId}/marks?${query}` : `subjects/${subjectId}/marks`
  return callFastapi<SubjectMarksGrid>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function saveSubjectMarks(
  subjectId: string,
  payload: MarksBatchSaveRequest,
): Promise<BffResult<MarksBatchSaveResponse>> {
  return mutateFastapi<MarksBatchSaveResponse>(
    `subjects/${subjectId}/marks`,
    "PUT",
    payload,
    [`subjects/${subjectId}/marks`, `subjects/${subjectId}`],
  )
}

export function getMarksChangeLog(
  subjectId: string,
  params: Pick<MarksQueryParams, "semester" | "academic_year" | "page" | "page_size"> = {},
): Promise<BffResult<MarksChangeLogResponse>> {
  const searchParams = new URLSearchParams()
  if (params.semester !== undefined) searchParams.set("semester", String(params.semester))
  if (params.academic_year !== undefined)
    searchParams.set("academic_year", params.academic_year ?? "")
  if (params.page) searchParams.set("page", String(params.page))
  if (params.page_size) searchParams.set("page_size", String(params.page_size))
  const query = searchParams.toString()
  const path = query ? `subjects/${subjectId}/marks/log?${query}` : `subjects/${subjectId}/marks/log`
  return callFastapi<MarksChangeLogResponse>(path, BFF_TTL_MS)
}

export type AttendanceSession = {
  day_name: string
  slot_no: number
  start_time: string
  end_time: string
  subject_id: string
  subject_name: string
  faculty_id: string
  lecture_type: string | null
  recorded_lectures: number | null
}

export type AttendanceEntryStudent = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  first_name: string
  last_name: string
  attendance_percentage: number | null
  attendance_status: string | null
  eligibility_status: string | null
  shortage_flag: string | null
}

export type AttendanceBands = {
  critical_threshold: number
  compliance_threshold: number
  excellent_threshold: number
  good_split: number
}

export type AttendanceEntryMeta = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  department_code: number
  sessions: AttendanceSession[]
  students: AttendanceEntryStudent[]
  bands: AttendanceBands
}

export type LectureStudentRow = {
  enrollment_record_id: string
  student_id: string
  enrollment_no: number
  first_name: string
  last_name: string
  attendance_id: number | null
  attendance_status: string | null
  attendance_percentage: number | null
  attendance_status_band: string | null
  eligibility_status: string | null
  shortage_flag: string | null
}

export type LectureAttendance = {
  subject_id: string
  subject_code: string
  subject_name: string
  semester_no: number
  academic_year: string
  lecture_date: string
  day_name: string
  slot_no: number
  start_time: string
  end_time: string
  lecture_type: string | null
  faculty_id: string
  faculty_name: string | null
  recorded: boolean
  lecture_number: number | null
  students: LectureStudentRow[]
  bands: AttendanceBands
}

export type LectureAttendanceStudentInput = {
  student_id: string
  attendance_status: "P" | "A"
}

export type LectureAttendanceSaveRequest = {
  semester_no: number
  academic_year: string
  lecture_date: string
  slot_no: number
  students: LectureAttendanceStudentInput[]
  allow_correction?: boolean
}

export type AttendanceSaveSummary = {
  inserted: number
  updated: number
  unchanged: number
}

export type LectureAttendanceSaveResult = {
  student_id: string
  enrollment_no: number
  operation: string
  attendance_status: string
  attendance_percentage: number | null
  attendance_status_band: string | null
  eligibility_status: string | null
  shortage_flag: string | null
  semester_attendance_percentage: number | null
  overall_attendance_percentage: number | null
}

export type LectureAttendanceSaveResponse = {
  subject_id: string
  semester_no: number
  academic_year: string
  lecture_date: string
  day_name: string
  slot_no: number
  lecture_number: number | null
  recorded: boolean
  summary: AttendanceSaveSummary
  students: LectureAttendanceSaveResult[]
  semester_attendance_percentage: number | null
  overall_attendance_percentage: number | null
  bands: AttendanceBands
}

export type AttendanceChangeLogItem = {
  change_id: number
  lecture_date: string
  slot_no: number
  student_id: string
  student_name: string | null
  subject_id: string
  field_name: string
  old_value: unknown
  new_value: unknown
  operation_type: string
  changed_by: string | null
  changed_at: string
}

export type AttendanceChangeLogResponse = {
  subject_id: string
  semester_no: number
  academic_year: string
  items: AttendanceChangeLogItem[]
  pagination: FacultyPagination
}

export type CorrectedAttendanceRecord = {
  attendance_id: number
  student_id: string
  subject_id: string
  lecture_date: string
  lecture_number: number
  operation: string
  attendance_status: string
  attendance_percentage: number | null
  attendance_status_band: string | null
  eligibility_status: string | null
  shortage_flag: string | null
  semester_attendance_percentage: number | null
  overall_attendance_percentage: number | null
}

export type AttendanceEntryParams = {
  semester?: number | null
  academic_year?: string | null
}

export type FacultyTimetableSession = {
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
  department_code: number | null
  faculty_id: string
}

export type FacultyTimetableDay = {
  day_name: string
  sessions: FacultyTimetableSession[]
}

export type FacultyTimetableSlot = {
  slot_no: number
  start_time: string
  end_time: string
}

export type FacultyTimetableResponse = {
  faculty_id: string
  semester_no: number
  academic_year: string
  total_sessions: number
  slots: FacultyTimetableSlot[]
  days: FacultyTimetableDay[]
}

export type FullTimetableResponse = {
  semester_no: number
  academic_year: string
  total_sessions: number
  slots: FacultyTimetableSlot[]
  days: FacultyTimetableDay[]
}

function appendAttendanceTermParams(
  searchParams: URLSearchParams,
  params: { semester?: number | null; academic_year?: string | null },
) {
  // Only set params that are actually usable. An empty academic_year or a NaN
  // semester (e.g. an empty "semester=" URL segment) must never reach FastAPI:
  // academic_year="" would resolve to a bogus term and semester=NaN fails its
  // Optional[int] coercion with HTTP 422.
  if (params.semester !== undefined && params.semester !== null && !Number.isNaN(params.semester)) {
    searchParams.set("semester", String(params.semester))
  }
  if (params.academic_year) searchParams.set("academic_year", params.academic_year)
}

export function getAttendanceEntryMeta(
  subjectId: string,
  params: AttendanceEntryParams = {},
  opts?: { bypassCache?: boolean },
): Promise<BffResult<AttendanceEntryMeta>> {
  const searchParams = new URLSearchParams()
  appendAttendanceTermParams(searchParams, params)
  const query = searchParams.toString()
  const path = query
    ? `subjects/${subjectId}/attendance/meta?${query}`
    : `subjects/${subjectId}/attendance/meta`
  return callFastapi<AttendanceEntryMeta>(path, BFF_TTL_MS, opts?.bypassCache)
}

export function getLectureAttendance(
  subjectId: string,
  params: {
    lecture_date: string
    slot_no: number
    semester?: number | null
    academic_year?: string | null
  },
  opts?: { bypassCache?: boolean },
): Promise<BffResult<LectureAttendance>> {
  const searchParams = new URLSearchParams()
  searchParams.set("lecture_date", params.lecture_date)
  searchParams.set("slot_no", String(params.slot_no))
  appendAttendanceTermParams(searchParams, params)
  const query = searchParams.toString()
  return callFastapi<LectureAttendance>(
    `subjects/${subjectId}/attendance/lecture?${query}`,
    BFF_TTL_MS,
    opts?.bypassCache,
  )
}

export function saveLectureAttendance(
  subjectId: string,
  payload: LectureAttendanceSaveRequest,
): Promise<BffResult<LectureAttendanceSaveResponse>> {
  return mutateFastapi<LectureAttendanceSaveResponse>(
    `subjects/${subjectId}/attendance/lecture`,
    "POST",
    payload,
    [
      `subjects/${subjectId}/attendance`,
      `attendance/`,
      `subjects/${subjectId}`,
      `dashboard/summary`,
    ],
  )
}

export function correctLectureAttendance(
  subjectId: string,
  attendanceId: number,
  status: "P" | "A",
): Promise<BffResult<CorrectedAttendanceRecord>> {
  return mutateFastapi<CorrectedAttendanceRecord>(
    `attendance/${attendanceId}`,
    "PATCH",
    { status },
    [
      `subjects/${subjectId}/attendance`,
      `attendance/`,
      `subjects/${subjectId}`,
      `dashboard/summary`,
    ],
  )
}

export function getAttendanceChangeLog(
  subjectId: string,
  params: AttendanceEntryParams & {
    page?: number
    page_size?: number
    lecture_date?: string
    slot_no?: number
  } = {},
): Promise<BffResult<AttendanceChangeLogResponse>> {
  const searchParams = new URLSearchParams()
  appendAttendanceTermParams(searchParams, params)
  if (params.lecture_date) searchParams.set("lecture_date", params.lecture_date)
  if (params.slot_no !== undefined && !Number.isNaN(params.slot_no))
    searchParams.set("slot_no", String(params.slot_no))
  if (params.page) searchParams.set("page", String(params.page))
  if (params.page_size) searchParams.set("page_size", String(params.page_size))
  const query = searchParams.toString()
  const path = query
    ? `subjects/${subjectId}/attendance/log?${query}`
    : `subjects/${subjectId}/attendance/log`
  return callFastapi<AttendanceChangeLogResponse>(path, BFF_TTL_MS)
}

export function getFacultyTimetable(
  params: AttendanceEntryParams = {},
): Promise<BffResult<FacultyTimetableResponse>> {
  const searchParams = new URLSearchParams()
  appendAttendanceTermParams(searchParams, params)
  const query = searchParams.toString()
  const path = query ? `timetable?${query}` : "timetable"
  return callFastapi<FacultyTimetableResponse>(path, BFF_TTL_MS)
}

export function getFullTimetable(
  params: AttendanceEntryParams = {},
): Promise<BffResult<FullTimetableResponse>> {
  const searchParams = new URLSearchParams()
  appendAttendanceTermParams(searchParams, params)
  const query = searchParams.toString()
  const path = query ? `timetable/full?${query}` : "timetable/full"
  return callFastapi<FullTimetableResponse>(path, BFF_TTL_MS)
}

export type FacultyNotificationTypeFilter =
  | "STUDENT_ATTENDANCE_WARNING"
  | "STUDENT_ELIGIBILITY_WARNING"
  | "STUDENT_PERFORMANCE_CHANGE"
  | "SYSTEM"

export type FacultyNotificationItem = {
  message_id: string
  message_type: string
  title: string
  message_body: string
  subject?: string | null
  priority: string
  status: string
  created_at: string
}

export type FacultyNotificationsResponse = {
  faculty_id: string
  items: FacultyNotificationItem[]
  total: number
  page: number
  page_size: number
  unread_count: number
}

export type FacultyUnreadCountResponse = {
  faculty_id: string
  unread_count: number
}

export type FacultyMarkAllReadResponse = {
  faculty_id: string
  updated_count: number
}

export type FacultyClearAllResponse = {
  faculty_id: string
  cleared_count: number
}

export function getFacultyNotifications(
  options?: {
    messageType?: FacultyNotificationTypeFilter
    unreadOnly?: boolean
    page?: number
    pageSize?: number
  },
): Promise<BffResult<FacultyNotificationsResponse>> {
  const searchParams = new URLSearchParams()
  if (options?.messageType) searchParams.set("message_type", options.messageType)
  if (options?.unreadOnly) searchParams.set("unread_only", "true")
  if (options?.page) searchParams.set("page", String(options.page))
  if (options?.pageSize) searchParams.set("page_size", String(options.pageSize))
  const query = searchParams.toString()
  const path = query ? `me/notifications?${query}` : "me/notifications"
  return callFastapi<FacultyNotificationsResponse>(path, BFF_TTL_MS, true)
}

export function getFacultyUnreadNotificationCount(): Promise<
  BffResult<FacultyUnreadCountResponse>
> {
  return callFastapi<FacultyUnreadCountResponse>("me/notifications/unread-count", BFF_TTL_MS, true)
}

export function markFacultyNotificationRead(
  messageId: string,
): Promise<BffResult<FacultyNotificationItem>> {
  return mutateFastapi<FacultyNotificationItem>(
    `me/notifications/${messageId}/read`,
    "PATCH",
    {},
    ["notifications"],
  )
}

export function markAllFacultyNotificationsRead(): Promise<
  BffResult<FacultyMarkAllReadResponse>
> {
  return mutateFastapi<FacultyMarkAllReadResponse>(
    "me/notifications/read-all",
    "POST",
    {},
    ["notifications"],
  )
}

export function clearFacultyNotification(
  messageId: string,
): Promise<BffResult<FacultyNotificationItem>> {
  return mutateFastapi<FacultyNotificationItem>(
    `me/notifications/${messageId}`,
    "DELETE",
    {},
    ["notifications"],
  )
}

export function clearAllFacultyNotifications(): Promise<
  BffResult<FacultyClearAllResponse>
> {
  return mutateFastapi<FacultyClearAllResponse>(
    "me/notifications",
    "DELETE",
    {},
    ["notifications"],
  )
}
