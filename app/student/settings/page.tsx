import { cookies } from "next/headers"

import { requireRole } from "@/lib/session"

import { PageHeader } from "@/components/shared/layout/page-header"
import { SettingsView } from "@/components/student/settings/settings-view"

type SessionInfo = {
  username: string | null
  role: string | null
  studentId: string | null
  department: string | null
}

async function readSessionInfo(): Promise<SessionInfo | null> {
  const cookieStore = await cookies()
  const raw = cookieStore.get("session")?.value
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as {
      username?: string
      role?: string
      student_id?: string | null
      department?: string | null
    } | null
    if (!parsed || typeof parsed !== "object") return null
    return {
      username: typeof parsed.username === "string" ? parsed.username : null,
      role: typeof parsed.role === "string" ? parsed.role : null,
      studentId: typeof parsed.student_id === "string" ? parsed.student_id : null,
      department: typeof parsed.department === "string" ? parsed.department : null,
    }
  } catch {
    return null
  }
}

export default async function SettingsPage() {
  await requireRole("Student")

  const session = await readSessionInfo()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Settings"
        description="Manage your preferences, notifications, security and session."
      />
      <SettingsView session={session} />
    </div>
  )
}
