import { requireRole } from "@/lib/session"
import { getFacultyNotifications } from "@/lib/faculty-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { NotificationsView } from "@/components/faculty/notifications/notifications-view"

export const dynamic = "force-dynamic"

const PAGE_SIZE = 20

export default async function NotificationsPage() {
  await requireRole("Faculty")

  const result = await getFacultyNotifications({ page: 1, pageSize: PAGE_SIZE })

  if (!result.ok) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <PageHeader
          title="Notifications"
          description="Alerts about student attendance, eligibility and performance."
        />
        <ErrorState title="Notifications unavailable" description={result.error.message} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title="Notifications"
        description="Alerts about student attendance, eligibility and performance."
        fetchedAt={result.fetchedAt}
      />
      <NotificationsView
        initial={result.data}
        initialPage={result.data.page}
        pageSize={PAGE_SIZE}
      />
    </div>
  )
}
