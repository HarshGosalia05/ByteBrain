import { Briefcase } from "lucide-react"

import { requireRole } from "@/lib/session"
import { PlaceholderPage } from "@/components/faculty/placeholder-page"

export default async function WorkloadPage() {
  await requireRole("Faculty")
  return (
    <PlaceholderPage
      title="Teaching Workload"
      description="Your teaching load — subjects, enrolled counts, sections and mentee overlap."
      icon={Briefcase}
    />
  )
}
