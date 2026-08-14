import { NextResponse } from "next/server"

import { changeStudentPassword } from "@/lib/student-api"

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { current_password?: string; new_password?: string }
    const currentPassword = String(body.current_password ?? "")
    const newPassword = String(body.new_password ?? "")

    if (!currentPassword || !newPassword) {
      return NextResponse.json(
        { ok: false, error: { status: 400, message: "Current and new password are required." } },
        { status: 400 },
      )
    }

    const result = await changeStudentPassword(currentPassword, newPassword)
    return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
  } catch {
    return NextResponse.json(
      { ok: false, error: { status: 400, message: "Invalid request payload." } },
      { status: 400 },
    )
  }
}
