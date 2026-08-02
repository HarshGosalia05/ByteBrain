import { BarChart3 } from "lucide-react"

import { requireRole } from "@/lib/session"
import { PlaceholderPage } from "@/components/faculty/placeholder-page"

export default async function PerformancePage() {
  await requireRole("Faculty")
  return (
    <PlaceholderPage
      title="Performance Analytics"
      description="Descriptive performance analytics with configurable learning-gap flags for everything you teach."
      icon={BarChart3}
    />
  )
}
