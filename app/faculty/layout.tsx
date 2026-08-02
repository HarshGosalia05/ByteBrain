import { requireRole } from "@/lib/session"
import { getFacultyProfile } from "@/lib/faculty-api"
import { FacultyShell } from "@/components/faculty/shell"

export default async function FacultyLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  await requireRole("Faculty")

  const profileResult = await getFacultyProfile()
  const profile = profileResult.ok ? profileResult.data : null

  return <FacultyShell profile={profile}>{children}</FacultyShell>
}
