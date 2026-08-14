import { requireRole } from "@/lib/session"
import { getStudentProfile, getStudentSettings } from "@/lib/student-api"
import { StudentShell } from "@/components/student/shell"
import { LanguageProvider, type SupportedLanguage } from "@/lib/i18n"

export default async function StudentLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  await requireRole("Student")

  const [profileResult, settingsResult] = await Promise.all([
    getStudentProfile(),
    getStudentSettings(),
  ])
  const profile = profileResult.ok ? profileResult.data : null
  const initialLanguage = (
    settingsResult.ok
      ? (settingsResult.data.namespaces.account?.display_language as SupportedLanguage)
      : "en"
  ) || "en"

  return (
    <LanguageProvider initialLanguage={initialLanguage}>
      <StudentShell profile={profile}>{children}</StudentShell>
    </LanguageProvider>
  )
}
