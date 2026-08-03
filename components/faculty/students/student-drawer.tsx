"use client"

import * as React from "react"
import { X, User, GraduationCap, Percent, Book, AlertTriangle } from "lucide-react"
import type { FacultyStudentOverview } from "@/lib/faculty-api"
import { fetchStudentOverviewAction } from "@/app/faculty/students/actions"
import { Button } from "@/components/ui/button"

export function StudentDrawer({
  studentId,
  onClose,
}: {
  studentId: string | null
  onClose: () => void
}) {
  const [data, setData] = React.useState<FacultyStudentOverview | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  
  const [prevStudentId, setPrevStudentId] = React.useState(studentId)
  if (studentId !== prevStudentId) {
    setPrevStudentId(studentId)
    setData(null)
  }

  React.useEffect(() => {
    if (!studentId) {
      return
    }

    let isMounted = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setError(null)

    fetchStudentOverviewAction(studentId).then((res) => {
      if (!isMounted) return
      if (res.ok) {
        setData(res.data)
      } else {
        setError(res.error.message)
      }
      setLoading(false)
    })

    return () => {
      isMounted = false
    }
  }, [studentId])

  // Handle escape key
  React.useEffect(() => {
    if (!studentId) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [studentId, onClose])

  if (!studentId) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity" 
        onClick={onClose} 
      />
      
      <div className="relative flex w-full max-w-md flex-col overflow-hidden border-l bg-card shadow-2xl animate-in slide-in-from-right duration-300 sm:w-[450px]">
        {/* Header */}
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="text-lg font-semibold tracking-tight">Student Profile</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : error ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2 text-destructive">
              <AlertTriangle className="size-8 opacity-50" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          ) : data ? (
            <div className="flex flex-col gap-8">
              {/* Profile Header */}
              <div className="flex items-start gap-4">
                <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xl font-bold text-primary">
                  {data.first_name[0]}{data.last_name[0]}
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="text-xl font-bold tracking-tight">
                    {data.first_name} {data.last_name}
                  </h3>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">{data.enrollment_no}</span>
                    <span>•</span>
                    <span>Semester {data.current_semester || "-"}</span>
                  </div>
                  {data.email && (
                    <p className="text-sm text-muted-foreground">{data.email}</p>
                  )}
                </div>
              </div>

              {/* Academic Summary */}
              <div className="flex flex-col gap-3">
                <h4 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                  Academic Summary
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <GraduationCap className="size-4" /> SGPA
                    </div>
                    <p className="mt-1 text-2xl font-semibold">
                      {data.latest_sgpa?.toFixed(2) || "-"}
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Percent className="size-4" /> Attendance
                    </div>
                    <p className="mt-1 text-2xl font-semibold">
                      {data.overall_attendance_percentage !== null 
                        ? `${data.overall_attendance_percentage.toFixed(1)}%` 
                        : "-"}
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Book className="size-4" /> Backlogs
                    </div>
                    <p className="mt-1 text-2xl font-semibold text-destructive">
                      {data.total_backlogs !== null ? data.total_backlogs : "-"}
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <User className="size-4" /> Standing
                    </div>
                    <p className="mt-1 text-lg font-semibold">
                      {data.academic_standing || "-"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Subject Summary */}
              {data.subject_performance.length > 0 && (
                <div className="flex flex-col gap-3">
                  <h4 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                    Current Subjects
                  </h4>
                  <div className="rounded-md border">
                    {data.subject_performance.map((sub, i) => (
                      <div 
                        key={sub.subject_code} 
                        className={`flex items-center justify-between p-3 ${
                          i !== data.subject_performance.length - 1 ? "border-b" : ""
                        }`}
                      >
                        <div className="flex flex-col min-w-0 pr-4">
                          <span className="text-sm font-medium truncate" title={sub.subject_name}>
                            {sub.subject_name}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {sub.subject_code}
                          </span>
                        </div>
                        <div className="flex flex-col items-end shrink-0">
                          <span className="text-sm font-semibold">
                            {sub.grade || "-"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {sub.attendance_percentage !== null 
                              ? `${sub.attendance_percentage.toFixed(0)}% att` 
                              : "-"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer Actions */}
        <div className="border-t p-4 bg-muted/10">
          <Button variant="outline" className="w-full" disabled={!data}>
            View Full Profile
          </Button>
        </div>
      </div>
    </div>
  )
}
