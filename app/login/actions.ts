"use server"

import { query } from "@/lib/db"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

export async function login(
  prevState: { error?: string } | undefined,
  formData: FormData,
) {
  const username = formData.get("username") as string
  const password = formData.get("password") as string

  if (!username || !password) {
    return { error: "Username and password are required" }
  }

  let user: { role: string } | undefined

  try {
    const result = await query(
      "SELECT user_id, username, role, department, student_id, faculty_id FROM users WHERE username = $1 AND password = $2 AND is_active = TRUE",
      [username, password],
    )

    if (result.rows.length === 0) {
      return { error: "Invalid username or password" }
    }

    const userRow = result.rows[0]
    user = userRow

    const cookieStore = await cookies()
    cookieStore.set("session", JSON.stringify(user), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      maxAge: 60 * 60 * 24,
      path: "/",
    })
  } catch (e) {
    return { error: `Error: ${e instanceof Error ? e.message : String(e)}` }
  }

  const roleDashboards: Record<string, string> = {
    Student: "/student/dashboard",
    Faculty: "/faculty/dashboard",
    Admin: "/admin/dashboard",
  }

  redirect(roleDashboards[user?.role ?? ""] ?? "/login")
}
