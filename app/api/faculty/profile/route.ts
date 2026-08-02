import { NextResponse } from "next/server"
import { getFacultyProfile, updateFacultyContact } from "@/lib/faculty-api"

export async function GET() {
  const result = await getFacultyProfile()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function PATCH(request: Request) {
  const input = (await request.json()) as { email?: string | null; phone_number?: number | null }
  const result = await updateFacultyContact(input)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
