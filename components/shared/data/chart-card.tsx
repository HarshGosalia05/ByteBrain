import type { LucideIcon } from "lucide-react"

import type { CsvColumn } from "@/lib/csv"
import { cn } from "@/lib/utils"

import { ExportButton } from "@/components/shared/data/export-button"
import { EmptyState } from "@/components/shared/state/empty-state"
import { ErrorState } from "@/components/shared/state/error-state"
import { Skeleton } from "@/components/ui/skeleton"

type ChartCardProps = {
  title: string
  subtitle?: string
  status?: "ready" | "loading" | "error" | "empty"
  emptyIcon?: LucideIcon
  emptyTitle?: string
  emptyDescription?: string
  errorTitle?: string
  errorDescription?: string
  exportFileName?: string
  exportColumns?: CsvColumn[]
  exportRows?: Array<Record<string, unknown>>
  children?: React.ReactNode
  className?: string
}

export function ChartCard({
  title,
  subtitle,
  status = "ready",
  emptyIcon,
  emptyTitle,
  emptyDescription,
  errorTitle = "Failed to load chart",
  errorDescription,
  exportFileName,
  exportColumns,
  exportRows,
  children,
  className,
}: ChartCardProps) {
  const canExport =
    status === "ready" &&
    Boolean(exportFileName) &&
    Boolean(exportColumns) &&
    Boolean(exportRows && exportRows.length > 0)

  return (
    <section className={cn("rounded-xl bg-card p-4 ring-1 ring-foreground/10 print:break-inside-avoid", className)}>
      <div className="mb-4 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {canExport && exportFileName && exportColumns && exportRows && (
          <ExportButton fileName={exportFileName} columns={exportColumns} rows={exportRows} />
        )}
      </div>

      {status === "loading" ? (
        <Skeleton className="h-52 w-full" />
      ) : status === "error" ? (
        <ErrorState title={errorTitle} description={errorDescription} />
      ) : status === "empty" ? (
        <EmptyState
          icon={emptyIcon}
          title={emptyTitle ?? "No data in this scope"}
          description={emptyDescription}
        />
      ) : (
        children
      )}
    </section>
  )
}
