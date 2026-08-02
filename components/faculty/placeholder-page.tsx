import type { LucideIcon } from "lucide-react"

import { PageHeader } from "@/components/shared/layout/page-header"
import { EmptyState } from "@/components/shared/state/empty-state"

export function PlaceholderPage({
  title,
  description,
  icon,
}: {
  title: string
  description: string
  icon: LucideIcon
}) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={icon}
        title="Coming in a later slice"
        description="This section is part of the Faculty Module V1 roadmap and will be implemented after the Dashboard and Profile are approved."
      />
    </div>
  )
}
