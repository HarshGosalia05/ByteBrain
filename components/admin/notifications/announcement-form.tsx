"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Send, Bell, CheckCircle2, AlertCircle } from "lucide-react"

import { broadcastAnnouncementAction } from "@/app/admin/notifications/actions"
import type { CreateAnnouncementInput } from "@/lib/admin-api"
import { ChartCard } from "@/components/shared/data/chart-card"

export function AnnouncementForm() {
  const router = useRouter()
  const [loading, setLoading] = React.useState(false)
  const [successMsg, setSuccessMsg] = React.useState<string | null>(null)
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null)

  const [title, setTitle] = React.useState("")
  const [message, setMessage] = React.useState("")
  const [type, setType] = React.useState<CreateAnnouncementInput["type"]>("ANNOUNCEMENT")
  const [targetAudience, setTargetAudience] = React.useState<CreateAnnouncementInput["target_audience"]>("both")
  const [priority, setPriority] = React.useState<CreateAnnouncementInput["priority"]>("Normal")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !message.trim()) {
      setErrorMsg("Please enter both title and message body.")
      return
    }

    setLoading(true)
    setSuccessMsg(null)
    setErrorMsg(null)

    const res = await broadcastAnnouncementAction({
      title: title.trim(),
      message: message.trim(),
      type,
      target_audience: targetAudience,
      priority,
    })

    setLoading(false)

    if (res.ok) {
      setSuccessMsg(
        `Announcement broadcast successfully! Notified ${res.data.recipients_notified} recipient(s).`,
      )
      setTitle("")
      setMessage("")
      router.refresh()
    } else {
      setErrorMsg(res.error.message || "Failed to broadcast announcement.")
    }
  }

  return (
    <ChartCard
      title="Create & Broadcast Announcement"
      subtitle="Send official notifications directly to student and faculty feeds"
      status="ready"
      emptyIcon={Bell}
      emptyTitle="Create Announcement"
      emptyDescription=""
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {successMsg && (
          <div className="flex items-center gap-2 rounded-md bg-success/10 p-3 text-xs font-medium text-success border border-success/20">
            <CheckCircle2 className="size-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {errorMsg && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-xs font-medium text-destructive border border-destructive/20">
            <AlertCircle className="size-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">
              Notice Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as CreateAnnouncementInput["type"])}
              className="h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs ring-offset-background outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="ANNOUNCEMENT">Announcement</option>
              <option value="ACADEMIC_NOTICE">Academic Notice</option>
              <option value="HOLIDAY">Holiday Notice</option>
              <option value="EVENT">Campus Event</option>
              <option value="SYSTEM_NOTICE">System Notice</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">
              Target Audience
            </label>
            <select
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value as CreateAnnouncementInput["target_audience"])}
              className="h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs ring-offset-background outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="both">Both (Students & Faculty)</option>
              <option value="students">Students Only</option>
              <option value="faculty">Faculty Only</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">
              Priority Level
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as CreateAnnouncementInput["priority"])}
              className="h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs ring-offset-background outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="Normal">Normal Priority</option>
              <option value="High">High Priority</option>
              <option value="Urgent">Urgent Priority</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1">
            Announcement Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. End Semester Examination Schedule Announcement"
            required
            className="h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1">
            Message Body
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Write the complete announcement details for student and faculty feeds…"
            rows={3}
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring resize-y"
          />
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-xs font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="size-3.5" />
            {loading ? "Broadcasting..." : "Broadcast Announcement"}
          </button>
        </div>
      </form>
    </ChartCard>
  )
}
