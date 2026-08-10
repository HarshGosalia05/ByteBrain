import { cookies } from "next/headers"

export type SessionUser = {
  user_id: string
  username: string
  role: string
  department?: string | null
  student_id?: string | null
  faculty_id?: string | null
}

export async function getSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies()
  const raw = cookieStore.get("session")?.value
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as SessionUser
    return parsed && typeof parsed === "object" ? parsed : null
  } catch {
    return null
  }
}
