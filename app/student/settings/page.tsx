import { requireRole } from "@/lib/session"
import { getSessionUser } from "@/lib/auth-jwt"
import { getStudentSettings } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { SettingsView } from "@/components/student/settings/settings-view"

type SessionInfo = {
  username: string | null
  role: string | null
  studentId: string | null
  department: string | null
}

async function readSessionInfo(): Promise<SessionInfo | null> {
  const user = await getSessionUser()
  if (!user) return null
  return {
    username: typeof user.username === "string" ? user.username : null,
    role: typeof user.role === "string" ? user.role : null,
    studentId: typeof user.student_id === "string" ? user.student_id : null,
    department: typeof user.department === "string" ? user.department : null,
  }
}

export default async function SettingsPage() {
  await requireRole("Student")

  const [session, settingsResult] = await Promise.all([
    readSessionInfo(),
    getStudentSettings(),
  ])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Settings"
        description="Manage your preferences, notifications, security and session."
      />
      <SettingsView
        session={session}
        initialSettings={settingsResult.ok ? settingsResult.data : null}
      />
    </div>
  )
}
