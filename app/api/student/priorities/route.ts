import { NextResponse } from "next/server"
import { getPriorities } from "@/lib/student-api"

export async function GET() {
  const result = await getPriorities()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
