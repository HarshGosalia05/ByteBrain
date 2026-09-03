import { requireRole } from "@/lib/session"
import { getSessionUser } from "@/lib/auth-jwt"
import { AdminShell } from "@/components/admin/shell"

export default async function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  await requireRole("Admin")

  const user = await getSessionUser()
  const username = user ? user.username ?? null : null

  return <AdminShell username={username}>{children}</AdminShell>
}
