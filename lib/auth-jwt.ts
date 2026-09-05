import { createHmac, timingSafeEqual } from "node:crypto"

export type SessionUser = {
  user_id: string
  username: string
  role: string
  department?: string | null
  student_id?: string | null
  faculty_id?: string | null
  token_version?: number
}

// Standard HS256 JWT helper (base64url). No external dependency.
function base64UrlEncode(data: string | Uint8Array): string {
  const str = typeof data === "string" ? data : Buffer.from(data).toString("binary")
  return Buffer.from(str, "binary")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "")
}

function base64UrlDecode(input: string): Buffer {
  const b64 = input.replace(/-/g, "+").replace(/_/g, "/")
  const pad = b64.length % 4 === 0 ? "" : "=".repeat(4 - (b64.length % 4))
  return Buffer.from(b64 + pad, "base64")
}

function hmacSignature(data: string, secret: string): string {
  return base64UrlEncode(createHmac("sha256", secret).update(data).digest())
}

function getJwtSecret(): string {
  const secret = process.env.JWT_SECRET
  if (!secret) {
    throw new Error("JWT_SECRET is not configured in the server environment.")
  }
  return secret
}

/** Sign a SessionUser into a standard HS256 JWT string. */
export function signSession(user: SessionUser): string {
  const nowSec = Math.floor(Date.now() / 1000)
  const payload = {
    ...user,
    iat: nowSec,
    exp: nowSec + 60 * 60 * 24, // 24 hours
  }
  const secret = getJwtSecret()
  const header = base64UrlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }))
  const body = base64UrlEncode(JSON.stringify(payload))
  const data = `${header}.${body}`
  const sig = hmacSignature(data, secret)
  return `${data}.${sig}`
}

/** Decode and verify an HS256 JWT. Throws on tampering/expiry/bad secret. */
export function verifySession(token: string): SessionUser {
  const secret = getJwtSecret()
  const parts = token.split(".")
  if (parts.length !== 3) {
    throw new Error("Malformed token")
  }
  const [header, body, sig] = parts
  const data = `${header}.${body}`

  const expectedSig = hmacSignature(data, secret)
  const expectedBuf = base64UrlDecode(expectedSig)
  const actualBuf = base64UrlDecode(sig)
  if (expectedBuf.length !== actualBuf.length || !timingSafeEqual(expectedBuf, actualBuf)) {
    throw new Error("Invalid token signature")
  }

  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(base64UrlDecode(body).toString("utf-8")) as Record<string, unknown>
  } catch {
    throw new Error("Malformed token payload")
  }

  const exp = payload.exp as number | undefined
  if (typeof exp !== "number" || exp * 1000 <= Date.now()) {
    throw new Error("Token expired")
  }

  if (!payload.user_id || !payload.username || !payload.role) {
    throw new Error("Missing required claims")
  }

  return payload as unknown as SessionUser
}

/** Read and verify the signed session cookie. Returns null when absent/invalid. */
export async function getSessionUser(): Promise<SessionUser | null> {
  const { cookies } = await import("next/headers")
  const cookieStore = await cookies()
  const raw = cookieStore.get("session")?.value
  if (!raw) return null
  try {
    return verifySession(raw)
  } catch {
    return null
  }
}

/** Read and verify the signed session cookie as a plain claims object. */
export async function getSessionClaims(): Promise<Record<string, unknown> | null> {
  const user = await getSessionUser()
  if (!user) return null
  return user as unknown as Record<string, unknown>
}

/** Return the raw signed JWT from the session cookie (for Authorization header). */
export async function getSessionToken(): Promise<string | null> {
  const { cookies } = await import("next/headers")
  const cookieStore = await cookies()
  return cookieStore.get("session")?.value ?? null
}
