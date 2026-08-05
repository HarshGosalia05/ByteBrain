import { NextResponse } from "next/server"

import { updateFacultySettings } from "@/lib/faculty-api"

export async function PATCH(
  request: Request,
  props: { params: Promise<{ namespace: string }> },
) {
  const { namespace } = await props.params
  const input = (await request.json()) as Record<string, unknown>
  const result = await updateFacultySettings(namespace, input)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
