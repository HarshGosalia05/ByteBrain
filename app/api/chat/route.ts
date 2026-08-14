import { NextRequest, NextResponse } from "next/server"
import { sendChatMessage } from "@/lib/chat-api"

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const result = await sendChatMessage(body)

    if (!result.success) {
      return NextResponse.json(
        { error: result.error.message, code: result.error.code },
        { status: result.error.status }
      )
    }

    return NextResponse.json(result.data)
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON request payload", code: "INVALID_REQUEST" },
      { status: 400 }
    )
  }
}
