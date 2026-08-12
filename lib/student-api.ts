import { getSessionUser } from "./student-session.ts"

export type { SessionUser } from "./student-session.ts"

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
