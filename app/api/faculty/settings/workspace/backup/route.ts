import { NextResponse } from "next/server"

import { getFacultySettingsBackup } from "@/lib/faculty-api"

export async function GET() {
  const result = await getFacultySettingsBackup()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
