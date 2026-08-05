import { NextResponse } from "next/server"

import { getFacultySettings } from "@/lib/faculty-api"

export async function GET() {
  const result = await getFacultySettings()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
