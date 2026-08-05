import type { LucideIcon } from "lucide-react"

import { EmptyState } from "@/components/shared/state/empty-state"

export function SectionPlaceholder({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon
  title: string
  description: string
}) {
  return (
    <EmptyState
      icon={Icon}
      title={`${title} settings`}
      description={description}
    />
  )
}
