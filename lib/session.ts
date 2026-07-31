import { cookies } from "next/headers"
import { redirect } from "next/navigation"

export const ROLE_DASHBOARDS = {
  Student: "/student/dashboard",
  Faculty: "/faculty/dashboard",
  Admin: "/admin/dashboard",
} as const

export type Role = keyof typeof ROLE_DASHBOARDS

export async function requireRole(role: Role): Promise<void> {
  const cookieStore = await cookies()
  const session = cookieStore.get("session")

  if (!session) {
    redirect("/login")
  }

  try {
    const user = JSON.parse(session.value) as { role?: string } | null
    if (!user || typeof user.role !== "string" || user.role !== role) {
      redirect("/login")
    }
  } catch {
    redirect("/login")
  }
}

export async function redirectBySession(): Promise<void> {
  const cookieStore = await cookies()
  const session = cookieStore.get("session")

  if (!session) {
    redirect("/login")
  }

  try {
    const user = JSON.parse(session.value) as { role?: string } | null
    if (!user || typeof user.role !== "string") {
      redirect("/login")
    }
    redirect(ROLE_DASHBOARDS[user.role as Role] ?? "/login")
  } catch {
    redirect("/login")
  }
}
