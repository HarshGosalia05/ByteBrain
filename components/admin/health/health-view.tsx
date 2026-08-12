import { GraduationCap } from "lucide-react"

import type { AdminStudentsData } from "@/lib/admin-api"

import { HealthFilterBar } from "@/components/admin/health/health-filter-bar"
import { HealthTable } from "@/components/admin/health/health-table"

export function HealthView({
  data,
  fetchedAt,
}: {
  data: AdminStudentsData
  fetchedAt: string
}) {
  const students = data.students
  const totalCount = data.students_total || students.length

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Lifestyle & Health</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Lifestyle and health intelligence derived from stored student data.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
          <GraduationCap className="size-3.5" />
          {totalCount} total student{totalCount === 1 ? "" : "s"}
        </span>
      </div>

      <HealthFilterBar filters={data.filters} />

      <HealthTable data={data} />

      <p className="text-xs text-muted-foreground">
        Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}