import { Award, BookOpen, ClipboardCheck, TrendingDown, TrendingUp } from "lucide-react"

import type { SubjectIntelligenceData, SubjectRow } from "@/lib/admin-api"

import { ChartCard } from "@/components/shared/data/chart-card"
import { HorizontalBars, type HorizontalBarItem } from "@/components/shared/charts/horizontal-bars"
import { SubjectFilterBar } from "@/components/admin/academic/subject-filter-bar"

function toFixed(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—"
  return value.toFixed(digits)
}

function withSuffix(value: number | null, suffix: string): string {
  if (value === null || value === undefined) return "—"
  return `${toFixed(value)}${suffix}`
}

function subjectBars(
  rows: SubjectRow[],
  pick: (row: SubjectRow) => number | null,
  display: (row: SubjectRow) => string,
): HorizontalBarItem[] {
  return rows.map((row) => ({
    id: row.subject_code,
    label: row.subject_name,
    value: pick(row) ?? 0,
    display: display(row),
    hint: row.subject_code,
  }))
}

function AssessmentAnalysisCard({
  data,
}: {
  data: SubjectIntelligenceData["assessment_analysis"]
}) {
  const items = data.map((component) => ({
    id: component.component,
    label: component.component,
    value: component.normalized_percentage ?? 0,
    display:
      component.normalized_percentage === null
        ? "—"
        : `${toFixed(component.normalized_percentage)}% (${toFixed(component.raw_average)}/${component.max_marks})`,
  }))

  return (
    <ChartCard
      title="Assessment Analysis"
      subtitle="Average marks per component, normalized to % of each component max"
      status={items.length > 0 ? "ready" : "empty"}
      emptyIcon={ClipboardCheck}
      emptyTitle="No assessment data"
      emptyDescription="There are no performance records in the current selection."
    >
      <HorizontalBars items={items} color="var(--chart-1)" />
      <p className="mt-3 text-xs text-muted-foreground">
        Marks scheme: Internal /20 · Mid-Sem /50 · End-Sem /70 · Total /140.
        Un-entered components (live semester) are not counted as zero.
      </p>
    </ChartCard>
  )
}

function TopSubjectsCard({ rows }: { rows: SubjectRow[] }) {
  return (
    <ChartCard
      title="Top Subjects"
      subtitle="Top 10 by average percentage (completed results only)"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={TrendingUp}
      emptyTitle="No top subjects"
      emptyDescription="No graded subjects in the current selection."
    >
      <HorizontalBars
        items={subjectBars(rows, (r) => r.avg_percentage, (r) => withSuffix(r.avg_percentage, "%"))}
        color="var(--chart-2)"
      />
    </ChartCard>
  )
}

function WeakSubjectsCard({ rows }: { rows: SubjectRow[] }) {
  return (
    <ChartCard
      title="Weak Subjects"
      subtitle="Bottom 10 by average percentage (completed results only)"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={TrendingDown}
      emptyTitle="No weak subjects"
      emptyDescription="No graded subjects in the current selection."
    >
      <HorizontalBars
        items={subjectBars(rows, (r) => r.avg_percentage, (r) => withSuffix(r.avg_percentage, "%"))}
        color="var(--chart-3)"
      />
    </ChartCard>
  )
}

function PassRateCard({ rows }: { rows: SubjectRow[] }) {
  return (
    <ChartCard
      title="Pass Rate"
      subtitle="Top 15 subjects by pass % (Pending excluded)"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={Award}
      emptyTitle="No pass-rate data"
      emptyDescription="No completed results in the current selection."
    >
      <HorizontalBars
        items={subjectBars(rows, (r) => r.pass_rate, (r) => withSuffix(r.pass_rate, "%"))}
        color="var(--chart-1)"
      />
    </ChartCard>
  )
}

function SubjectTable({ rows }: { rows: SubjectRow[] }) {
  return (
    <ChartCard
      title="Subjects"
      subtitle="Subject-level averages in the selected scope"
      status={rows.length > 0 ? "ready" : "empty"}
      emptyIcon={BookOpen}
      emptyTitle="No subjects"
      emptyDescription="No subjects match the current filters."
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-200 text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase">
              <th className="py-2 pr-4 font-medium">Subject</th>
              <th className="py-2 pr-4 font-medium">Department</th>
              <th className="py-2 pr-4 text-right font-medium">Sem</th>
              <th className="py-2 pr-4 text-right font-medium">Students</th>
              <th className="py-2 pr-4 text-right font-medium">Avg Internal</th>
              <th className="py-2 pr-4 text-right font-medium">Avg Mid-Sem</th>
              <th className="py-2 pr-4 text-right font-medium">Avg End-Sem</th>
              <th className="py-2 pr-4 text-right font-medium">Avg %</th>
              <th className="py-2 pr-4 text-right font-medium">Pass Rate</th>
              <th className="py-2 text-right font-medium">Avg Attendance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.subject_code}-${row.semester}`} className="border-b last:border-0">
                <td className="py-2.5 pr-4">
                  <p className="max-w-56 truncate font-medium" title={`${row.subject_name} (${row.subject_code})`}>
                    {row.subject_name}
                  </p>
                  <p className="text-xs text-muted-foreground">{row.subject_code}</p>
                </td>
                <td className="py-2.5 pr-4">
                  <span className="text-xs">{row.department_name}</span>
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{row.semester}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{row.student_count}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{toFixed(row.avg_internal)}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{toFixed(row.avg_mid_sem)}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{toFixed(row.avg_end_sem)}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{withSuffix(row.avg_percentage, "%")}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{withSuffix(row.pass_rate, "%")}</td>
                <td className="py-2.5 text-right tabular-nums">{withSuffix(row.avg_attendance, "%")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  )
}

export function AcademicSubjectsView({
  data,
  fetchedAt,
}: {
  data: SubjectIntelligenceData
  fetchedAt: string
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Subject Intelligence</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Subject-level performance, marks-component analysis, and pass rates from live data.
          </p>
        </div>
      </div>

      <SubjectFilterBar filters={data.filters} />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-3">
          <AssessmentAnalysisCard data={data.assessment_analysis} />
        </div>
        <TopSubjectsCard rows={data.top_subjects} />
        <WeakSubjectsCard rows={data.weak_subjects} />
        <PassRateCard rows={data.pass_rate_ranking} />
      </div>

      <SubjectTable rows={data.subjects} />

      <p className="text-xs text-muted-foreground">
        Data refreshed {fetchedAt ? new Date(fetchedAt).toLocaleString() : "just now"}
      </p>
    </div>
  )
}
