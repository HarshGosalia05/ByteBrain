import { NextResponse } from "next/server"
import { clearAdminBffCache, getMLGenerationStatus } from "@/lib/admin-api"

export async function GET(
  _request: Request,
  context: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await context.params
  if (!jobId) {
    return NextResponse.json({ ok: false, error: { status: 400, message: "Missing job id" } })
  }
  const result = await getMLGenerationStatus(jobId)
  // When the background job settles, invalidate the BFF cache so the
  // freshly persisted predictions show up on the next intelligence load.
  if (result.ok) {
    const status = result.data.status
    if (status === "completed" || status === "failed" || status === "cancelled") {
      clearAdminBffCache()
    }
  }
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}