"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"

const LIMIT_OPTIONS = [25, 50, 100] as const

type StudentsPaginationProps = {
  total: number
  limit: number
  offset: number
}

export function StudentsPagination({
  total,
  limit,
  offset,
}: StudentsPaginationProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const safeLimit = LIMIT_OPTIONS.includes(limit as (typeof LIMIT_OPTIONS)[number])
    ? limit
    : 50
  const totalPages = Math.max(1, Math.ceil(total / safeLimit))
  const currentPage = Math.min(
    Math.max(1, Math.floor(offset / safeLimit) + 1),
    totalPages,
  )
  const shownFrom = total === 0 ? 0 : (currentPage - 1) * safeLimit + 1
  const shownTo = Math.min(total, currentPage * safeLimit)

  const goToPage = (page: number) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", String(page))
    if (page > 1) {
      params.set("limit", String(safeLimit))
    }
    router.push(`${pathname}?${params.toString()}`)
  }

  const handleLimitChange = (value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("limit", value)
    params.delete("page")
    router.push(`${pathname}?${params.toString()}`)
  }

  const buttonClassName =
    "flex h-9 items-center gap-1 rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:pointer-events-none disabled:opacity-50"

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Showing {shownFrom}–{shownTo} of {total} students
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>Rows</span>
          <select
            value={safeLimit}
            onChange={(e) => handleLimitChange(e.target.value)}
            aria-label="Students per page"
            className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {LIMIT_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <p className="text-xs text-muted-foreground tabular-nums">
          Page {currentPage} of {totalPages}
        </p>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="Previous page"
            className={buttonClassName}
          >
            <ChevronLeft className="size-4" />
            Prev
          </button>
          <button
            type="button"
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= totalPages}
            aria-label="Next page"
            className={cn(buttonClassName, "flex-row-reverse")}
          >
            <ChevronRight className="size-4" />
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
