import { NextResponse } from "next/server"
import {
  getGoals,
  createGoal,
  type GoalCreateInput,
} from "@/lib/student-api"

const GOAL_TYPES = ["target_sgpa", "target_percentage", "target_attendance"]

export async function GET() {
  const result = await getGoals()
  return NextResponse.json(result, { status: result.ok ? 200 : result.error.status })
}

export async function POST(request: Request) {
  let body: GoalCreateInput
  try {
    body = (await request.json()) as GoalCreateInput
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
    typeof body.target_value !== "number" ||
    !Number.isFinite(body.target_value) ||
    !GOAL_TYPES.includes(body.goal_type)
  ) {
    return NextResponse.json(
      {
        ok: false,
        error: { status: 422, code: "invalid", message: "The submitted value is not valid." },
      },
      { status: 422 },
    )
  }
  const result = await createGoal(body)
  return NextResponse.json(result, { status: result.ok ? 201 : result.error.status })
}
