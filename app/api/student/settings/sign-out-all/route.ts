import { NextResponse } from "next/server"

import { signOutAllStudentDevices } from "@/lib/student-api"

export async function POST() {
  const result = await signOutAllStudentDevices()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
