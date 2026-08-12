import { requireRole } from "@/lib/session"
import { getAdminAnnouncements, getExecutiveSummary } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { ExecutiveSummaryCard } from "@/components/admin/notifications/executive-summary-card"
import { AnnouncementForm } from "@/components/admin/notifications/announcement-form"
import { AnnouncementsList } from "@/components/admin/notifications/announcements-list"

export default async function AdminNotificationsPage() {
  await requireRole("Admin")

  const [execRes, annRes] = await Promise.all([
    getExecutiveSummary(),
    getAdminAnnouncements(),
  ])

  if (!execRes.ok) {
    return (
      <ErrorState
        title="Failed to load executive summary"
        description={execRes.error.message}
      />
    )
  }

  const announcements = annRes.ok ? annRes.data.announcements : []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Notifications & Executive Insights
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Broadcast official announcements to student and faculty feeds and review grounded executive insights.
        </p>
      </div>

      <ExecutiveSummaryCard data={execRes.data} />

      <div className="grid gap-6 lg:grid-cols-2">
        <AnnouncementForm />
        <AnnouncementsList announcements={announcements} />
      </div>
    </div>
  )
}
