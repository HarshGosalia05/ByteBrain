import { Users } from "lucide-react"

import { requireRole } from "@/lib/session"
import { PlaceholderPage } from "@/components/faculty/placeholder-page"

export default async function StudentsPage() {
  await requireRole("Faculty")
  return (
    <PlaceholderPage
      title="Students"
      description="Your classes and mentees — two distinct lists backed by teaching assignments and the mentorship map."
      icon={Users}
    />
  )
}
