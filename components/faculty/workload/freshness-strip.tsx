"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useTransition } from "react"
import { Database, RefreshCw } from "lucide-react"

import { refreshWorkloadDataAction } from "@/app/faculty/workload/actions"
import type { WorkloadSummaryParams } from "@/lib/faculty-api"

import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type WorkloadFreshnessStripProps = {
  fetchedAt: string | null
  scopeLabel: string
  filters: WorkloadSummaryParams
}

export function WorkloadFreshnessStrip({
  fetchedAt,
  scopeLabel,
  filters,
}: WorkloadFreshnessStripProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [pending, startTransition] = useTransition()

  const handleRefresh = () => {
    startTransition(async () => {
      const page = searchParams.get("page")
      const pageNum = page ? parseInt(page, 10) || 1 : 1
      const num = (key: string): number | undefined => {
        const raw = searchParams.get(key)
        if (!raw) return undefined
        const n = Number(raw)
        return Number.isFinite(n) ? n : undefined
      }
      await refreshWorkloadDataAction(filters, {
        semester: filters.semester,
        academic_year: filters.academic_year,
        subject_id: filters.subject_id,
        page: pageNum,
        page_size: 10,
        search: searchParams.get("search"),
        subject_type: searchParams.get("subject_type"),
        credits_min: num("credits_min"),
        credits_max: num("credits_max"),
        hours_min: num("hours_min"),
        hours_max: num("hours_max"),
        students_min: num("students_min"),
        students_max: num("students_max"),
        workload_status: searchParams.get("workload_status"),
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
