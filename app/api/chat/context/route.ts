import { NextResponse } from "next/server"
import { fetchPortalContext } from "@/lib/chat-api"

export async function GET() {
  try {
    const result = await fetchPortalContext()

    if (!result.success) {
      return NextResponse.json(
        { error: result.error.message, code: result.error.code },
        { status: result.error.status }
      )
    }

    return NextResponse.json(result.data)
  } catch {
    return NextResponse.json(
      { error: "Unable to load portal context", code: "INVALID_REQUEST" },
      { status: 400 }
    )
  }
}