import { History } from "lucide-react"

import type { AttemptHistoryItem } from "@/lib/student-api"

import { Badge } from "@/components/ui/badge"
import { GradeBadge } from "@/components/shared/data/grade-badge"
import { EmptyState } from "@/components/shared/state/empty-state"
import { cn } from "@/lib/utils"

function ResultBadge({ result }: { result: string | null }) {
  if (result === null) {
    return <Badge variant="muted">—</Badge>
  }
  const normalized = result.toUpperCase()
  const variant =
    normalized === "PASS" ? "success" : normalized === "FAIL" ? "destructive" : "secondary"
  return <Badge variant={variant}>{result}</Badge>
}

export function AttemptHistory({ items }: { items: AttemptHistoryItem[] }) {
  const withAttempts = items.filter((item) => item.has_multiple_attempts)

  if (withAttempts.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="Previous attempts are not available"
        description="Attempt history appears here when a subject has multiple recorded attempts."
      />
    )
  }

  return (
    <section className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <h2 className="text-sm font-semibold">Attempt history</h2>
      <p className="mt-1 mb-4 text-xs text-muted-foreground">
        Subjects with multiple recorded attempts, ordered by attempt number.
      </p>
      <div className="flex flex-col gap-4">
        {withAttempts.map((item) => (
          <div key={item.subject_code} className="overflow-x-auto rounded-lg bg-muted/40">
            <div className="flex flex-wrap items-center justify-between gap-2 px-3 pt-3">
              <div>
                <p className="text-sm font-medium">{item.subject_name}</p>
                <p className="text-xs text-muted-foreground">{item.subject_code}</p>
              </div>
              {item.improvement !== null && (
                <Badge variant={item.improvement >= 0 ? "success" : "destructive"}>
                  {item.improvement >= 0 ? "+" : ""}
                  {item.improvement.toFixed(0)} pts
                </Badge>
              )}
            </div>
            <table className="w-full min-w-[560px] text-sm">
              <caption className="sr-only">Attempts for {item.subject_name}</caption>
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pl-3 pr-4 font-medium">
                    Attempt
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Semester
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Academic year
                  </th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">
                    Percentage
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Grade
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Result
                  </th>
                </tr>
              </thead>
              <tbody>
                {item.attempts.map((attempt) => (
                  <tr
                    key={`${item.subject_code}-${attempt.attempt_number}`}
                    className={cn("border-b last:border-0", attempt.attempt_number === 1 && "")}
                  >
                    <td className="py-2 pl-3 pr-4 font-medium tabular-nums">
                      Attempt {attempt.attempt_number}
                    </td>
                    <td className="py-2 pr-4">Sem {attempt.semester}</td>
                    <td className="py-2 pr-4">
                      {attempt.academic_year ?? <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {attempt.percentage !== null ? (
                        `${attempt.percentage.toFixed(2)}%`
                      ) : (
                        <span className="text-muted-foreground">Pending</span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <GradeBadge grade={attempt.grade} />
                    </td>
                    <td className="py-2 pr-4">
                      <ResultBadge result={attempt.result_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  )
}
