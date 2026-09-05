"use server"

import { query } from "@/lib/db"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { signSession, type SessionUser } from "@/lib/auth-jwt"
import bcrypt from "bcryptjs"
import { checkRateLimit, resetRateLimit } from "@/lib/rate-limit"

const LOGIN_RATE_LIMIT = 10 // attempts per minute
const LOGIN_WINDOW_MS = 60_000

export async function login(
  prevState: { error?: string } | undefined,
  formData: FormData,
) {
  const username = formData.get("username") as string
  const password = formData.get("password") as string

  if (!username || !password) {
    return { error: "Username and password are required" }
  }

  // Rate limit by username to prevent brute-force.
  const rateKey = `login:${username.toLowerCase()}`
  const { allowed, retryAfterMs } = checkRateLimit(rateKey, LOGIN_RATE_LIMIT, LOGIN_WINDOW_MS)
  if (!allowed) {
    const retrySeconds = Math.ceil(retryAfterMs / 1000)
    return {
      error: `Too many login attempts. Please try again in ${retrySeconds} seconds.`,
    }
  }

  let user: { role: string } | undefined

  try {
    let userRow: {
      user_id: string
      username: string
      password: string
      role: string
      department?: string | null
      student_id?: string | null
      faculty_id?: string | null
      token_version?: number
    }

    try {
      const result = await query(
        "SELECT user_id, username, password, role, department, student_id, faculty_id, token_version FROM users WHERE username = $1 AND is_active = TRUE",
        [username],
      )
      if (result.rows.length === 0) {
        return { error: "Invalid username or password" }
      }
      userRow = result.rows[0] as typeof userRow
    } catch (queryErr: unknown) {
      const errMsg = queryErr instanceof Error ? queryErr.message : String(queryErr)
      if (errMsg.includes("token_version")) {
        // Fallback for database instances where token_version column migration has not been applied yet
        const result = await query(
          "SELECT user_id, username, password, role, department, student_id, faculty_id FROM users WHERE username = $1 AND is_active = TRUE",
          [username],
        )
        if (result.rows.length === 0) {
          return { error: "Invalid username or password" }
        }
        userRow = { ...result.rows[0], token_version: 1 } as typeof userRow
      } else {
        throw queryErr
      }
    }

    const storedHash = (userRow.password as string) || ""

    // Support both bcrypt hashes and legacy plaintext passwords.
    // Legacy passwords start with a non-$ character; bcrypt hashes always
    // start with "$2a$", "$2b$", or "$2y$".
    const isBcryptHash =
      storedHash.startsWith("$2a$") ||
      storedHash.startsWith("$2b$") ||
      storedHash.startsWith("$2y$")

    const passwordValid = isBcryptHash
      ? await bcrypt.compare(password, storedHash)
      : password === storedHash

    if (!passwordValid) {
      return { error: "Invalid username or password" }
    }

    // Successful login — reset rate limit for this user.
    resetRateLimit(rateKey)

    // Migrate legacy plaintext to bcrypt on successful login.
    if (!isBcryptHash) {
      const newHash = await bcrypt.hash(password, 12)
      await query("UPDATE users SET password = $1 WHERE user_id = $2", [
        newHash,
        userRow.user_id,
      ])
    }

    user = userRow

    // Sign a verifiable JWT before storing so the backend can trust the
    // token instead of the previous forgeable base64-JSON session.
    const session = signSession({
      user_id: userRow.user_id,
      username: userRow.username,
      role: userRow.role,
      department: userRow.department,
      student_id: userRow.student_id,
      faculty_id: userRow.faculty_id,
      token_version: userRow.token_version ?? 1,
    } as unknown as SessionUser)

    const cookieStore = await cookies()
    cookieStore.set("session", session, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24,
      path: "/",
    })
  } catch (e) {
    // Log the full error server-side; return a safe generic message.
    console.error("[login] Authentication error:", e)
    return { error: "An unexpected error occurred. Please try again." }
  }

  const roleDashboards: Record<string, string> = {
    Student: "/student/dashboard",
    Faculty: "/faculty/dashboard",
    Admin: "/admin/dashboard",
  }

  const normalizedRole = user?.role
    ? user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase()
    : ""

  redirect(
    roleDashboards[user?.role ?? ""] ??
      roleDashboards[normalizedRole] ??
      "/login",
  )
}
