import { NextResponse } from "next/server"

import { setStudentTwoFactor } from "@/lib/student-api"

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { enabled?: boolean; method?: string }
    const enabled = Boolean(body.enabled)
    const method = typeof body.method === "string" ? body.method : "email"

    const result = await setStudentTwoFactor(enabled, method)
    return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
  } catch {
    return NextResponse.json(
      { ok: false, error: { status: 400, message: "Invalid request payload." } },
      { status: 400 },
    )
  }
}
