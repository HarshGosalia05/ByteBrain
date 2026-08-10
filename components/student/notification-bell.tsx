"use client"

import * as React from "react"
import Link from "next/link"
import { Bell } from "lucide-react"

import type { BffResult, UnreadCountResponse } from "@/lib/student-api"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function NotificationBell() {
  const [count, setCount] = React.useState<number | null>(null)

  React.useEffect(() => {
    let cancelled = false
    async function refresh() {
      try {
        const res = await fetch("/api/student/notifications/unread-count", { cache: "no-store" })
        const result = (await res.json()) as BffResult<UnreadCountResponse>
        if (!cancelled && result.ok) {
          setCount(result.data.unread_count)
        }
      } catch {
        // Keep the last known value; the badge is best-effort.
      }
    }
    void refresh()
    const timer = window.setInterval(refresh, 60_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  return (
    <Link
      href="/student/notifications"
      aria-label="Notifications"
      title="Notifications"
      className={cn(
        buttonVariants({ variant: "ghost", size: "icon" }),
        "relative",
      )}
    >
      <Bell className="size-4" />
      {count !== null && count > 0 && (
        <span
          className="absolute top-0.5 right-0.5 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-semibold text-white"
          aria-label={`${count} unread notifications`}
        >
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  )
}
