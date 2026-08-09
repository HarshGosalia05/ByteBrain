"use client"

import { CalendarDays, Clock, GraduationCap } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import type {
  FacultyTimetableDay,
  FacultyTimetableResponse,
} from "@/lib/faculty-api"

function formatTime(value: string): string {
  if (!value) return ""
  const [hours, minutes] = value.split(":")
  if (hours === undefined || minutes === undefined) return value
  return `${hours}:${minutes}`
}

export function TimetableView({ data }: { data: FacultyTimetableResponse }) {
  if (data.total_sessions === 0) {
    return (
      <div className="flex flex-col gap-6">
        <section className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Time Table</h1>
          <p className="text-sm text-muted-foreground">
            Sem {data.semester_no} · {data.academic_year}
          </p>
        </section>
        <EmptyState
          icon={CalendarDays}
          title="No Timetable"
          description="No weekly timetable sessions are scheduled for you in this term yet."
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Time Table</h1>
        <p className="text-sm text-muted-foreground">
          Sem {data.semester_no} · {data.academic_year} · {data.total_sessions} scheduled session
          {data.total_sessions === 1 ? "" : "s"}
        </p>
      </section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.days.map((day: FacultyTimetableDay) => (
          <section
            key={day.day_name}
            className="flex flex-col gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
          >
            <h2 className="text-sm font-semibold">{day.day_name}</h2>
            <ul className="flex flex-col gap-2">
              {day.sessions.map((session) => (
                <li
                  key={session.timetable_id}
                  className="rounded-lg bg-muted/50 p-3 ring-1 ring-foreground/5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="min-w-0 text-sm font-medium">
                      {session.subject_code ? `${session.subject_code} · ` : ""}
                      {session.subject_name}
                    </p>
                    <Badge variant="secondary">
                      <Clock className="mr-1 size-3" />
                      Slot {session.slot_no}
                    </Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>
                      {formatTime(session.start_time)}–{formatTime(session.end_time)}
                    </span>
                    {session.lecture_type && (
                      <Badge variant="muted">{session.lecture_type}</Badge>
                    )}
                    {session.credits !== null && session.credits !== undefined && (
                      <span className="inline-flex items-center gap-1">
                        <GraduationCap className="size-3" />
                        {session.credits} credit{session.credits === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
