import { ShieldCheck, Users } from "lucide-react"

import type { BenchmarkItem } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import { cn } from "@/lib/utils"

function fmtPercentage(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(2)}%`
}

export function ClassBenchmark({ items }: { items: BenchmarkItem[] }) {
  const availableCount = items.filter((item) => item.available).length

  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <div className="mb-4">
        <h2 className="text-sm font-semibold">Class benchmark</h2>
        <p className="mt-1 flex items-start gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-3 shrink-0" />
          Class average across classmates with published results in the same subject, semester and
          year (minimum 5). Only aggregates — no peer identities are shown.
        </p>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Class comparison is unavailable"
          description="It requires at least 5 classmates with published results in the same subject, semester and year."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <caption className="sr-only">Student versus class average</caption>
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th scope="col" className="py-3 pr-4 font-medium">
                  Subject
                </th>
                <th scope="col" className="py-3 pr-4 font-medium">
                  Semester
                </th>
                <th scope="col" className="py-3 pr-4 text-right font-medium">
                  Your %
                </th>
                <th scope="col" className="py-3 pr-4 text-right font-medium">
                  Class avg
                </th>
                <th scope="col" className="py-3 pr-4 text-right font-medium">
                  Difference
                </th>
                <th scope="col" className="py-3 pr-4 text-right font-medium">
                  Cohort
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={`${item.subject_code}-${item.semester}`}
                  className={cn(
                    "border-b transition-colors last:border-0 hover:bg-muted/40",
                    !item.available && "opacity-60",
                  )}
                >
                  <td className="py-2.5 pr-4">
                    <span className="font-medium whitespace-nowrap">{item.subject_name}</span>
                    <span className="block text-xs text-muted-foreground">
                      {item.subject_code}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">Sem {item.semester}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {fmtPercentage(item.your_percentage)}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {item.available ? (
                      fmtPercentage(item.class_average)
                    ) : (
                      <span className="text-muted-foreground">
                        Class comparison unavailable
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {item.available && item.difference !== null ? (
                      <span
                        className={cn(
                          "font-medium",
                          item.difference >= 0 ? "text-chart-2" : "text-destructive",
                        )}
                      >
                        {item.difference >= 0 ? "+" : ""}
                        {item.difference.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-right">
                    <Badge variant="muted">{item.cohort_size} peers</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {items.length > 0 && availableCount === 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Class comparison is unavailable for all listed subjects until at least 5 classmates have
          published results for the same subject, semester and year.
        </p>
      )}
    </section>
  )
}
