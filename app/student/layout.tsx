import { requireRole } from "@/lib/session"
import { StudentShell } from "@/components/student/shell"

export default async function StudentLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  await requireRole("Student")

  return <StudentShell>{children}</StudentShell>
}
