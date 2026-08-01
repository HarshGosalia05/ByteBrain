import { Bell } from "lucide-react"

import { requireRole } from "@/lib/session"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"

export default async function NotificationsPage() {
  await requireRole("Student")

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Notifications" description="Alerts about your academic standing." />
      <EmptyState
        icon={Bell}
        title="No notifications yet"
        description="At-risk alerts, faculty messages and AI-driven insights will appear here in a future phase."
      />
    </div>
  )
}
