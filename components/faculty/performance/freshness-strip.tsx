"use client"

import { useRouter } from "next/navigation"
import { useTransition } from "react"
import { Database, RefreshCw } from "lucide-react"

import { refreshPerformanceSummaryAction } from "@/app/faculty/performance/actions"
import type { PerformanceSummaryParams } from "@/lib/faculty-api"

import { FreshnessBadge } from "@/components/shared/data/freshness-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type FreshnessStripProps = {
  fetchedAt: string | null
  scopeLabel: string
  filters: PerformanceSummaryParams
}

export function FreshnessStrip({ fetchedAt, scopeLabel, filters }: FreshnessStripProps) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  const handleRefresh = () => {
    startTransition(async () => {
      await refreshPerformanceSummaryAction(filters)
      router.refresh()
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl bg-card px-4 py-3 text-xs text-muted-foreground ring-1 ring-foreground/10">
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
