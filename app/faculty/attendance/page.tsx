import { CalendarCheck } from "lucide-react"

import { requireRole } from "@/lib/session"
import { PlaceholderPage } from "@/components/faculty/placeholder-page"

export default async function AttendancePage() {
  await requireRole("Faculty")
  return (
    <PlaceholderPage
      title="Attendance Analytics"
      description="Attendance trends with configurable low-attendance flags and attendance-vs-performance views."
      icon={CalendarCheck}
    />
  )
}
