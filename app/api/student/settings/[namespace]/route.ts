import { NextResponse } from "next/server"

import { updateStudentSettings } from "@/lib/student-api"

export async function PATCH(
  request: Request,
  props: { params: Promise<{ namespace: string }> },
) {
  const { namespace } = await props.params
  const input = (await request.json()) as Record<string, unknown>
  const result = await updateStudentSettings(namespace, input)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
