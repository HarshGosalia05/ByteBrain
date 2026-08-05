import { NextResponse } from "next/server"

import { importFacultySettings } from "@/lib/faculty-api"

export async function POST(request: Request) {
  const input = (await request.json().catch(() => ({}))) as { payload?: Record<string, unknown> }
  const result = await importFacultySettings(input.payload ?? {})
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
