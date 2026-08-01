import { Settings } from "lucide-react"

import { requireRole } from "@/lib/session"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"

export default async function SettingsPage() {
  await requireRole("Student")

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Settings" description="Account and preference management." />
      <EmptyState
        icon={Settings}
        title="Settings are coming soon"
        description="Theme switching is already available from the header. Account preferences and notification controls will arrive in a future phase."
      />
    </div>
  )
}
