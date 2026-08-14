import { NextResponse } from "next/server"

import { getStudentSettings } from "@/lib/student-api"

export async function GET() {
  const result = await getStudentSettings()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
