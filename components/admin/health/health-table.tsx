import { GraduationCap, Moon, BookOpen, Tv } from "lucide-react"

import type { AdminStudentRow } from "@/lib/admin-api"

import { ChartCard } from "@/components/shared/data/chart-card"
import { StatCard } from "@/components/shared/data/stat-card"

function derivePhysicalHealthScore(
  activity: string | null | undefined,
  sleepHours: number | null | undefined,
): number | null {
  if (!activity && (sleepHours === null || sleepHours === undefined)) {
    return null
  }
  const act = (activity || "").toLowerCase()
  const sleep = sleepHours ?? 7.0

  if (act === "regular") {
    if (sleep >= 7.5) return 5
    if (sleep >= 6.5) return 4
    return 3
  }
  if (act === "moderate") {
    if (sleep >= 7.0) return 4
    if (sleep >= 6.0) return 3
    return 2
  }
  if (act === "rare") {
    if (sleep >= 7.0) return 3
    if (sleep >= 5.5) return 2
    return 1
  }
  if (sleep >= 7.5) return 4
  if (sleep >= 6.0) return 3
  return 2
}

function deriveMentalHealthScore(
  wellbeing: string | null | undefined,
  stressLevel: string | null | undefined,
): number | null {
  if (!wellbeing && !stressLevel) {
    return null
  }
  const wb = (wellbeing || "").toLowerCase()
  const stress = (stressLevel || "").toLowerCase()

  let base = 3
  if (wb === "excellent") base = 5
  else if (wb === "good") base = 4
  else if (wb === "average") base = 3
  else if (wb === "poor") base = 1

  if (stress === "high" && base > 1) {
    base -= 1
  } else if (stress === "low" && base < 5 && base >= 3) {
    base += 1
  }

  return Math.min(5, Math.max(1, base))
}

const ScoreBadge = ({
  score,
  label,
}: {
  score: number | null
  label?: string | null
}) => {
  if (score === null || score === undefined) return <span className="text-muted-foreground">—</span>
  const styles: Record<number, string> = {
    1: "bg-destructive/10 text-destructive",
    2: "bg-chart-4/20 text-chart-4",
    3: "bg-chart-3/20 text-chart-3",
    4: "bg-chart-2/20 text-chart-2",
    5: "bg-success/10 text-success",
  }
  const labels: Record<number, string> = {
    1: "Critical",
    2: "Watch",
    3: "Average",
    4: "Good",
    5: "Excellent",
  }
  const style = styles[score] ?? "text-muted-foreground"
  const text = label || labels[score] || String(score)
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ${style}`}>
      <span className="font-bold">{score}/5</span>
      <span>•</span>
      <span>{text}</span>
    </span>
  )
}

export function HealthTable({ data }: { data: { students: AdminStudentRow[] } }) {
  const students = data.students

  const sleepValues = students
    .map((s) => s.average_sleep_hours)
    .filter((v): v is number => typeof v === "number" && !isNaN(v))
  const studyValues = students
    .map((s) => s.daily_study_hours)
    .filter((v): v is number => typeof v === "number" && !isNaN(v))
  const screenValues = students
    .map((s) => s.screen_time_hours)
    .filter((v): v is number => typeof v === "number" && !isNaN(v))

  const avgSleepStr =
    sleepValues.length > 0
      ? `${(sleepValues.reduce((a, b) => a + b, 0) / sleepValues.length).toFixed(1)} hrs`
      : "—"
  const avgStudyStr =
    studyValues.length > 0
      ? `${(studyValues.reduce((a, b) => a + b, 0) / studyValues.length).toFixed(1)} hrs`
      : "—"
  const avgScreenStr =
    screenValues.length > 0
      ? `${(screenValues.reduce((a, b) => a + b, 0) / screenValues.length).toFixed(1)} hrs`
      : "—"

  return (
    <ChartCard
      title="Lifestyle & Health Intelligence"
      subtitle="Aggregated directly from stored student lifestyle survey & health indicators"
      status={students.length > 0 ? "ready" : "empty"}
      emptyIcon={GraduationCap}
      emptyTitle="No health data"
      emptyDescription="No students match the current filters."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Students"
          value={students.length > 0 ? students.length.toString() : "0"}
          icon={GraduationCap}
          tone="primary"
        />
        <StatCard
          label="Avg Sleep Duration"
          value={avgSleepStr}
          icon={Moon}
          tone="success"
        />
        <StatCard
          label="Avg Daily Study"
          value={avgStudyStr}
          icon={BookOpen}
          tone="primary"
        />
        <StatCard
          label="Avg Screen Time"
          value={avgScreenStr}
          icon={Tv}
          tone="warning"
        />
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-200 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Student</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 font-medium">Sleep / Study / Screen</th>
              <th className="py-2 pr-4 font-medium">Physical Health</th>
              <th className="py-2 pr-4 font-medium">Mental Health & Stress</th>
              <th className="py-2 pr-4 font-medium">Support Status</th>
            </tr>
          </thead>
          <tbody>
            {students.map((row) => {
              const physScore = derivePhysicalHealthScore(
                row.physical_activity,
                row.average_sleep_hours,
              )
              const mentScore = deriveMentalHealthScore(
                row.mental_wellbeing,
                row.stress_level,
              )
              return (
                <tr key={row.student_id} className="border-b last:border-0">
                  <td className="py-2.5 pr-4">
                    <p className="max-w-52 truncate font-medium">{row.student_name}</p>
                    <p className="text-xs text-muted-foreground">{row.student_id}</p>
                  </td>
                  <td className="py-2.5 pr-4 text-xs">{row.department_name || "—"}</td>
                  <td className="py-2.5 pr-4 text-xs tabular-nums">
                    {row.average_sleep_hours != null || row.daily_study_hours != null ? (
                      <span>
                        Sleep: {row.average_sleep_hours ?? "—"}h | Study: {row.daily_study_hours ?? "—"}h
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2.5 pr-4">
                    <ScoreBadge
                      score={physScore}
                      label={row.physical_activity ? `${row.physical_activity}` : undefined}
                    />
                  </td>
                  <td className="py-2.5 pr-4">
                    <ScoreBadge
                      score={mentScore}
                      label={
                        row.mental_wellbeing
                          ? `${row.mental_wellbeing} (${row.stress_level ?? "Medium"} Stress)`
                          : undefined
                      }
                    />
                  </td>
                  <td className="py-2.5">
                    {row.risk ? (
                      <span
                        className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                          row.risk !== "At Risk" && row.risk !== "High" && row.risk !== "Critical"
                            ? "bg-success/10 text-success"
                            : "bg-destructive/10 text-destructive"
                        }`}
                      >
                        {row.risk}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Showing {students.length} student{students.length === 1 ? "" : "s"} in the selected scope
      </p>
    </ChartCard>
  )
}