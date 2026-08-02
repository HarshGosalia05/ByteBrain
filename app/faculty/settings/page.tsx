import { Settings } from "lucide-react"

import { requireRole } from "@/lib/session"
import { PlaceholderPage } from "@/components/faculty/placeholder-page"

export default async function SettingsPage() {
  await requireRole("Faculty")
  return (
    <PlaceholderPage
      title="Settings"
      description="Account and preference settings, consistent with the platform auth flow."
      icon={Settings}
    />
  )
}
