export type UserRole = "Student" | "Faculty" | "Admin"

export interface StudentPortalSnapshot {
  name?: string | null
  department?: string | null
  currentSemester?: number | null
  academicYear?: string | null
  cgpa?: number | null
  sgpa?: number | null
  percentage?: number | null
  backlogs?: number | null
  academicStanding?: string | null
  overallAttendance?: number | null
  topSubjects?: string[]
  weakSubjects?: string[]
  predictionsAvailable?: boolean
  careerDomain?: string | null
  nextClasses?: string[]
  notificationCount?: number
}

export interface FacultyPortalSnapshot {
  name?: string | null
  department?: string | null
  designation?: string | null
  subjectsTaught?: string[]
  menteeCount?: number | null
  flaggedCount?: number
  totalStudents?: number | null
  avgCgpa?: number | null
  avgAttendance?: number | null
}

export interface AdminPortalSnapshot {
  totalStudents?: number | null
  totalFaculty?: number | null
  totalDepartments?: number | null
  overallCgpa?: number | null
  overallAttendance?: number | null
  flaggedCount?: number
  departmentNames?: string[]
}

export interface PortalSnapshot {
  role: UserRole
  student?: StudentPortalSnapshot | null
  faculty?: FacultyPortalSnapshot | null
  admin?: AdminPortalSnapshot | null
  available: boolean
}

export interface UIMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
  status?: "success" | "clarification" | "unauthorized" | "unavailable" | "error"
  intent?: string | null
  toolName?: string | null
  verifiedSources?: string[]
  provider?: string | null
  model?: string | null
  isError?: boolean
}

export interface ChatbotProps {
  role?: UserRole
  targetStudentId?: string | null
  pageContext?: string | null
  className?: string
}