"use client"

import * as React from "react"
import {
  Bell,
  CalendarCheck,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"

import type {
  BffResult,
  FacultyNotificationItem,
  FacultyNotificationsResponse,
  FacultyNotificationTypeFilter,
} from "@/lib/faculty-api"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/shared/state/empty-state"

const FILTERS: { value: FacultyNotificationTypeFilter | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "STUDENT_ATTENDANCE_WARNING", label: "Attendance" },
  { value: "STUDENT_ELIGIBILITY_WARNING", label: "Eligibility" },
  { value: "STUDENT_PERFORMANCE_CHANGE", label: "Performance" },
  { value: "SYSTEM", label: "System" },
]

const typeMeta: Record<string, { label: string; icon: typeof Bell }> = {
  STUDENT_ATTENDANCE_WARNING: { label: "Attendance", icon: CalendarCheck },
  STUDENT_ELIGIBILITY_WARNING: { label: "Eligibility", icon: ShieldAlert },
  STUDENT_PERFORMANCE_CHANGE: { label: "Performance", icon: TrendingUp },
  SYSTEM: { label: "System", icon: Bell },
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function NotificationsView({
  initial,
  initialPage,
  pageSize,
}: {
  initial: FacultyNotificationsResponse
  initialPage: number
  pageSize: number
}) {
  const [filter, setFilter] = React.useState<FacultyNotificationTypeFilter | "ALL">("ALL")
  const [items, setItems] = React.useState<FacultyNotificationItem[]>(initial.items)
  const [total, setTotal] = React.useState(initial.total)
  const [unreadCount, setUnreadCount] = React.useState(initial.unread_count)
  const [page, setPage] = React.useState(initialPage)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  async function load(
    nextFilter: FacultyNotificationTypeFilter | "ALL",
    nextPage: number,
  ) {
    setBusy(true)
    setError(null)
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(pageSize) })
    if (nextFilter !== "ALL") params.set("message_type", nextFilter)
    try {
      const res = await fetch(`/api/faculty/notifications?${params.toString()}`, {
        cache: "no-store",
      })
      const result = (await res.json()) as BffResult<FacultyNotificationsResponse>
      if (result.ok) {
        setItems(result.data.items)
        setTotal(result.data.total)
        setUnreadCount(result.data.unread_count)
        setPage(result.data.page)
      } else {
        setError(result.error.message)
      }
    } catch {
      setError("Could not load notifications. Try again.")
    } finally {
      setBusy(false)
    }
  }

  function applyFilter(nextFilter: FacultyNotificationTypeFilter | "ALL") {
    if (nextFilter === filter) return
    setFilter(nextFilter)
    void load(nextFilter, 1)
  }

  function goTo(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages || nextPage === page) return
    void load(filter, nextPage)
  }

  async function markRead(messageId: string) {
    setItems((current) =>
      current.map((item) =>
        item.message_id === messageId ? { ...item, status: "Read" } : item,
      ),
    )
    setUnreadCount((count) => Math.max(0, count - 1))
    try {
      await fetch(`/api/faculty/notifications/${messageId}/read`, { method: "PATCH" })
    } catch {
      // keep optimistic state
    }
  }

  async function markAllRead() {
    setItems((current) => current.map((item) => ({ ...item, status: "Read" })))
    setUnreadCount(0)
    try {
      await fetch("/api/faculty/notifications/read-all", { method: "POST" })
    } catch {
      // keep optimistic state
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          className="flex flex-wrap items-center gap-1.5"
          role="tablist"
          aria-label="Filter notifications"
        >
          {FILTERS.map((option) => (
            <button
              key={option.value}
              role="tab"
              aria-selected={filter === option.value}
              onClick={() => applyFilter(option.value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                filter === option.value
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={unreadCount > 0 ? "warning" : "muted"}>
            {unreadCount} unread
          </Badge>
          {unreadCount > 0 && (
            <Button variant="outline" size="sm" onClick={() => void markAllRead()}>
              <CheckCheck className="size-3" />
              Mark all as read
            </Button>
          )}
        </div>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {busy ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Loading notifications…</p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="No notifications"
          description={
            filter === "ALL"
              ? "When student attendance, eligibility or performance needs attention, alerts will appear here."
              : "No notifications match this filter."
          }
        />
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Notification list">
          {items.map((item) => {
            const meta = typeMeta[item.message_type] ?? { label: item.message_type, icon: Bell }
            const Icon = meta.icon
            const unread = item.status !== "Read"
            return (
              <li
                key={item.message_id}
                className={`rounded-xl bg-card p-4 ring-1 transition-colors ${
                  unread ? "ring-foreground/15" : "ring-foreground/10"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
                      unread ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <Icon className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {unread && (
                        <span className="size-1.5 rounded-full bg-primary" aria-label="Unread" />
                      )}
                      <p className="text-sm font-medium">{item.title}</p>
                      {item.subject && <Badge variant="outline">{item.subject}</Badge>}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{item.message_body}</p>
                    <div className="mt-2 flex items-center gap-3">
                      <span className="text-xs text-muted-foreground">
                        {formatDate(item.created_at)}
                      </span>
                      <span className="text-xs text-muted-foreground">{meta.label}</span>
                      {unread && (
                        <Button
                          variant="ghost"
                          size="xs"
                          className="ml-auto"
                          onClick={() => markRead(item.message_id)}
                        >
                          <CheckCheck className="size-3" />
                          Mark as read
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => goTo(page - 1)}
              disabled={page <= 1 || busy}
            >
              <ChevronLeft className="size-3" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => goTo(page + 1)}
              disabled={page >= totalPages || busy}
            >
              Next
              <ChevronRight className="size-3" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
