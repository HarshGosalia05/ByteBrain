import { NextResponse } from "next/server"
import { getGoal, updateGoal, type GoalUpdateInput } from "@/lib/student-api"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ goalId: string }> },
) {
  const { goalId } = await params
  const result = await getGoal(goalId)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ goalId: string }> },
) {
  const { goalId } = await params
  let body: GoalUpdateInput
  try {
    body = (await request.json()) as GoalUpdateInput
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 400, code: "invalid", message: "Invalid request body." },
      },
      { status: 400 },
    )
  }
  if (
    body.target_value !== undefined &&
    body.target_value !== null &&
    (typeof body.target_value !== "number" || !Number.isFinite(body.target_value))
  ) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 422, code: "invalid", message: "The submitted value is not valid." },
      },
      { status: 422 },
    )
  }
  if (
    body.status !== undefined &&
    body.status !== null &&
    body.status !== "Active" &&
    body.status !== "Inactive"
  ) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 422, code: "invalid", message: "The submitted value is not valid." },
      },
      { status: 422 },
    )
  }
  const result = await updateGoal(goalId, body)
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}
