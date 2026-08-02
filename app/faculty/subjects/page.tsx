import { BookOpen } from "lucide-react"

import { requireRole } from "@/lib/session"
import { PlaceholderPage } from "@/components/faculty/placeholder-page"

export default async function SubjectsPage() {
  await requireRole("Faculty")
  return (
    <PlaceholderPage
      title="Subjects"
      description="Subjects you teach, with enrollment, performance and attendance per subject."
      icon={BookOpen}
    />
  )
}
