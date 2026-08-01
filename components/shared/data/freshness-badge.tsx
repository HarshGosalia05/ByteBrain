"use client"

import * as React from "react"

import { Badge } from "@/components/ui/badge"

let lastTick = Date.now()

function subscribe(callback: () => void) {
  const timer = window.setInterval(() => {
    lastTick = Date.now()
    callback()
  }, 60_000)
  return () => window.clearInterval(timer)
}

function getSnapshot() {
  return lastTick
}

function formatRelative(iso: string, now: number): string {
  const diffMs = now - new Date(iso).getTime()
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" })
  const minutes = Math.round(diffMs / 60_000)
  if (Math.abs(minutes) < 1) return rtf.format(0, "minute")
  if (Math.abs(minutes) < 60) return rtf.format(-minutes, "minute")
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return rtf.format(-hours, "hour")
  return rtf.format(Math.round(hours / 24), "day")
}

export function FreshnessBadge({ fetchedAt }: { fetchedAt?: string | null }) {
  const now = React.useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  if (!fetchedAt) return null
  return <Badge variant="muted">Updated {formatRelative(fetchedAt, now)}</Badge>
}
