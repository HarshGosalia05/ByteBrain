import { NextResponse } from "next/server"

import { resetFacultySettings } from "@/lib/faculty-api"
import type { SettingsResetLevel } from "@/lib/faculty-api"

export async function POST(request: Request) {
  const input = (await request.json().catch(() => ({}))) as {
    level?: SettingsResetLevel
    include_profile_extra?: boolean
  }
  const result = await resetFacultySettings(
    input.level ?? "workspace",
    input.include_profile_extra === true,
  )
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
