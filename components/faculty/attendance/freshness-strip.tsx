"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useTransition } from "react"
import { Database, RefreshCw } from "lucide-react"

import { refreshAttendanceDataAction } from "@/app/faculty/attendance/actions"
import type { AttendanceSummaryParams } from "@/lib/faculty-api"

import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type AttendanceFreshnessStripProps = {
  fetchedAt: string | null
  scopeLabel: string
  filters: AttendanceSummaryParams
}

export function AttendanceFreshnessStrip({
  fetchedAt,
  scopeLabel,
  filters,
}: AttendanceFreshnessStripProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [pending, startTransition] = useTransition()

  const handleRefresh = () => {
    startTransition(async () => {
      const page = searchParams.get("page")
      const pageNum = page ? parseInt(page, 10) || 1 : 1
      await refreshAttendanceDataAction(filters, {
        semester: filters.semester,
        academic_year: filters.academic_year,
        subject_id: filters.subject_id,
        page: pageNum,
        page_size: 10,
        search: searchParams.get("search"),
        attendance_range: searchParams.get("attendance_range"),
        attendance_status: searchParams.get("attendance_status"),
        defaulter_status: searchParams.get("defaulter_status"),
        student_status: searchParams.get("student_status"),
        sort: searchParams.get("sort") || "name",
        order: (searchParams.get("order") as "asc" | "desc") || "asc",
      })
      router.push(`${pathname}?${searchParams.toString()}`)
      router.refresh()
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl bg-card px-4 py-3 text-xs text-muted-foreground ring-1 ring-foreground/10 print:hidden">
      <div className="flex items-center gap-1.5">
        <span className="font-medium text-foreground">Last updated</span>
        <FreshnessBadge fetchedAt={fetchedAt} />
      </div>
      <div className="flex items-center gap-1.5">
        <span className="font-medium text-foreground">Source</span>
        <span className="inline-flex items-center gap-1 font-medium text-chart-2">
          <Database className="size-3.5" />
          Real Database
        </span>
      </div>
      <div className="flex min-w-0 items-center gap-1.5">
        <span className="font-medium text-foreground">Scope</span>
        <span className="truncate">{scopeLabel}</span>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="ml-auto"
        disabled={pending}
        onClick={handleRefresh}
      >
        <RefreshCw className={cn("size-3.5", pending && "animate-spin")} />
        Refresh
      </Button>
    </div>
  )
}
