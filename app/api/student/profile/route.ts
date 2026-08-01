import { NextResponse } from "next/server"
import { getStudentProfile } from "@/lib/student-api"

export async function GET() {
  const result = await getStudentProfile()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
