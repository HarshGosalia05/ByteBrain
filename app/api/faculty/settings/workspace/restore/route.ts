import { NextResponse } from "next/server"

import { restoreFacultySettings } from "@/lib/faculty-api"

export async function POST() {
  const result = await restoreFacultySettings()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
