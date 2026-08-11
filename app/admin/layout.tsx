import { cookies } from "next/headers"

import { requireRole } from "@/lib/session"
import { AdminShell } from "@/components/admin/shell"

export default async function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  await requireRole("Admin")

  const cookieStore = await cookies()
  const raw = cookieStore.get("session")?.value
  let username: string | null = null
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as { username?: string }
      username = typeof parsed.username === "string" ? parsed.username : null
    } catch {
      username = null
    }
  }

  return <AdminShell username={username}>{children}</AdminShell>
}
