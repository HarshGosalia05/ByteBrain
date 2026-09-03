import type { UserRole } from "@/components/shared/chatbot/types"

/**
 * Page/route context identifiers sent to the chatbot backend as a context hint.
 * These are allowlisted server-side; the backend drops any value it does not
 * recognize or that is not valid for the authenticated role.
 *
 * This is context ONLY - it is never treated as authorization.
 */
export const PAGE_CONTEXTS = {
  // Student
  STUDENT_ML_INSIGHTS: "student_ml_insights",
  STUDENT_ATTENDANCE: "student_attendance",
  STUDENT_SUBJECTS: "student_subjects",
  STUDENT_ACADEMIC: "student_academic",
  STUDENT_PROFILE: "student_profile",
  STUDENT_DASHBOARD: "student_dashboard",
  STUDENT_REPORT_CARD: "student_report_card",
  STUDENT_TIMETABLE: "student_timetable",
  STUDENT_SETTINGS: "student_settings",
  STUDENT_NOTIFICATIONS: "student_notifications",
  // Faculty
  FACULTY_STUDENT_PROFILE: "faculty_student_profile",
  FACULTY_STUDENTS: "faculty_students",
  FACULTY_DASHBOARD: "faculty_dashboard",
  FACULTY_SUBJECTS: "faculty_subjects",
  FACULTY_PERFORMANCE: "faculty_performance",
  FACULTY_ATTENDANCE: "faculty_attendance",
  FACULTY_WORKLOAD: "faculty_workload",
  FACULTY_PROFILE: "faculty_profile",
  // Admin
  ADMIN_ANALYTICS: "admin_analytics",
  ADMIN_DASHBOARD: "admin_dashboard",
  ADMIN_RISK: "admin_risk",
  ADMIN_ML_INTELLIGENCE: "admin_ml_intelligence",
  ADMIN_CAREER: "admin_career",
  ADMIN_ACADEMIC: "admin_academic",
  ADMIN_ATTENDANCE: "admin_attendance",
  ADMIN_STUDENTS: "admin_students",
} as const

export type PageContextValue = (typeof PAGE_CONTEXTS)[keyof typeof PAGE_CONTEXTS]

/**
 * Map the current route/pathname to a page-context identifier for a role.
 * Only known routes map to a context; anything else returns null so the
 * backend treats the request as having no page context.
 */
export function derivePageContext(pathname: string | null | undefined, role: UserRole): PageContextValue | null {
  const path = pathname ?? ""

  if (role === "Student") {
    if (path.startsWith("/student/ml-insights")) return PAGE_CONTEXTS.STUDENT_ML_INSIGHTS
    if (path.startsWith("/student/attendance")) return PAGE_CONTEXTS.STUDENT_ATTENDANCE
    if (path.startsWith("/student/subjects")) return PAGE_CONTEXTS.STUDENT_SUBJECTS
    if (path.startsWith("/student/academic")) return PAGE_CONTEXTS.STUDENT_ACADEMIC
    if (path.startsWith("/student/profile")) return PAGE_CONTEXTS.STUDENT_PROFILE
    if (path.startsWith("/student/report-card")) return PAGE_CONTEXTS.STUDENT_REPORT_CARD
    if (path.startsWith("/student/timetable")) return PAGE_CONTEXTS.STUDENT_TIMETABLE
    if (path.startsWith("/student/settings")) return PAGE_CONTEXTS.STUDENT_SETTINGS
    if (path.startsWith("/student/notifications")) return PAGE_CONTEXTS.STUDENT_NOTIFICATIONS
    if (path.startsWith("/student/dashboard")) return PAGE_CONTEXTS.STUDENT_DASHBOARD
    return null
  }

  if (role === "Faculty") {
    // /faculty/students/<studentId> and its sub-routes (ml-insights etc.)
    if (path.startsWith("/faculty/students/")) return PAGE_CONTEXTS.FACULTY_STUDENT_PROFILE
    if (path.startsWith("/faculty/students")) return PAGE_CONTEXTS.FACULTY_STUDENTS
    if (path.startsWith("/faculty/subjects")) return PAGE_CONTEXTS.FACULTY_SUBJECTS
    if (path.startsWith("/faculty/performance")) return PAGE_CONTEXTS.FACULTY_PERFORMANCE
    if (path.startsWith("/faculty/attendance")) return PAGE_CONTEXTS.FACULTY_ATTENDANCE
    if (path.startsWith("/faculty/workload")) return PAGE_CONTEXTS.FACULTY_WORKLOAD
    if (path.startsWith("/faculty/profile")) return PAGE_CONTEXTS.FACULTY_PROFILE
    if (path.startsWith("/faculty/dashboard")) return PAGE_CONTEXTS.FACULTY_DASHBOARD
    return null
  }

  // Admin
  if (path.startsWith("/admin/analytics")) return PAGE_CONTEXTS.ADMIN_ANALYTICS
  if (path.startsWith("/admin/ml-intelligence")) return PAGE_CONTEXTS.ADMIN_ML_INTELLIGENCE
  if (path.startsWith("/admin/ml-insights")) return PAGE_CONTEXTS.ADMIN_ML_INTELLIGENCE
  if (path.startsWith("/admin/risk")) return PAGE_CONTEXTS.ADMIN_RISK
  if (path.startsWith("/admin/career")) return PAGE_CONTEXTS.ADMIN_CAREER
  if (path.startsWith("/admin/academic")) return PAGE_CONTEXTS.ADMIN_ACADEMIC
  if (path.startsWith("/admin/attendance")) return PAGE_CONTEXTS.ADMIN_ATTENDANCE
  if (path.startsWith("/admin/students")) return PAGE_CONTEXTS.ADMIN_STUDENTS
  if (path.startsWith("/admin/dashboard")) return PAGE_CONTEXTS.ADMIN_DASHBOARD
  if (path === "/admin" || path.startsWith("/admin")) return PAGE_CONTEXTS.ADMIN_DASHBOARD
  return null
}
