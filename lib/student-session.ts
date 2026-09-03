import { cookies } from "next/headers"
import { verifySession, type SessionUser } from "./auth-jwt"

export type { SessionUser } from "./auth-jwt"
export { getSessionToken } from "./auth-jwt"

export async function getSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies()
  const raw = cookieStore.get("session")?.value
  if (!raw) return null
  try {
    return verifySession(raw)
  } catch {
    return null
  }
}
