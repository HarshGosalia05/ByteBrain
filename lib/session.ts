import { redirect } from "next/navigation"
import { getSessionUser } from "./auth-jwt"

export const ROLE_DASHBOARDS = {
  Student: "/student/dashboard",
  Faculty: "/faculty/dashboard",
  Admin: "/admin/dashboard",
} as const

export type Role = keyof typeof ROLE_DASHBOARDS

export async function requireRole(role: Role): Promise<void> {
  const user = await getSessionUser()

  if (!user || typeof user.role !== "string" || user.role !== role) {
    redirect("/login")
  }
}

export async function redirectBySession(): Promise<void> {
  const user = await getSessionUser()

  if (!user || typeof user.role !== "string") {
    redirect("/login")
  }
  redirect(ROLE_DASHBOARDS[user.role as Role] ?? "/login")
}
