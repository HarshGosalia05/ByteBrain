import { requireRole } from "@/lib/session"
import { getStudentProfile } from "@/lib/student-api"
import { StudentShell } from "@/components/student/shell"

export default async function StudentLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  await requireRole("Student")

  const profileResult = await getStudentProfile()
  const profile = profileResult.ok ? profileResult.data : null

  return <StudentShell profile={profile}>{children}</StudentShell>
}
