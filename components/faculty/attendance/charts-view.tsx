"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  BarChart3,
  BookOpen,
  GitCompareArrows,
  GraduationCap,
  Gauge,
  Split,
  Target,
  TrendingUp,
} from "lucide-react"

import { SubjectBarChart, type ChartReferenceLine } from "@/components/shared/charts/bar-chart"
import { ScatterChart } from "@/components/shared/charts/scatter-chart"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { ChartCard } from "@/components/shared/data/chart-card"
import { scopeStamp } from "@/lib/csv"
import type {
  AttendanceCorrelation,
  AttendanceDistributions,
  AttendanceSubjectBreakdown,
  AttendanceThresholds,
  AttendanceTrends,
} from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"

type ChartsViewProps = {
  distributions: SectionResult<AttendanceDistributions>
  subjectBreakdown: SectionResult<AttendanceSubjectBreakdown>
  trends: SectionResult<AttendanceTrends>
  correlation: SectionResult<AttendanceCorrelation>
  thresholds: AttendanceThresholds
}

function baselineLine(value: number): { y: number; label: string } {
  return { y: value, label: `Baseline ${value}%` }
}

function parseBandUpperBound(value: string): number | null {
  const range = value.match(/(\d+)\s*%?\s*-\s*(\d+)/)
  if (range) return Number(range[2])
  const below = value.match(/<+\s*(\d+)/)
  if (below) return Number(below[1])
  if (/>=+\s*\d+/.test(value)) return Number.POSITIVE_INFINITY
  return null
}

function bandBoundaryLines(
  bands: Array<{ label: string; count: number }>,
  lines: Array<{ value: number; label: string }>,
): ChartReferenceLine[] {
  return lines.flatMap((line) => {
    let boundary: string | undefined
    for (const band of bands) {
      const upper = parseBandUpperBound(band.label)
      if (upper === null) continue
      if (upper <= line.value) boundary = band.label
    }
    if (!boundary) return []
    return [{ x: boundary, position: "end", label: line.label }]
  })
}

export function ChartsView({
  distributions,
  subjectBreakdown,
  trends,
  correlation,
  thresholds,
}: ChartsViewProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const handleSubjectClick = (entry: Record<string, string | number>) => {
    const subjectId = String(entry.subject_id ?? "")
    const params = new URLSearchParams(searchParams.toString())
    if (subjectId) {
      params.set("subject_id", subjectId)
    } else {
      params.delete("subject_id")
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  const scope = scopeStamp([
    searchParams.get("academic_year"),
    searchParams.get("semester") ? `sem${searchParams.get("semester")}` : null,
    searchParams.get("subject_id"),
  ])

  const distError = distributions.error
  const subjError = subjectBreakdown.error
  const trendError = trends.error
  const corrError = correlation.error

  const distData = distributions.data
  const statusData = (distData?.status_distribution ?? []).map((d) => ({
    label: d.label,
    count: d.count,
  }))
  const bandData = (distData?.attendance_bands ?? []).map((b) => ({
    label: b.label,
    count: b.count,
  }))
  const aboveBelowData = (distData?.above_below ?? []).map((a) => ({
    label: a.label,
    count: a.count,
  }))

  const subjectRows = subjectBreakdown.data?.items ?? []
  const subjectAvg = subjectRows.map((s) => ({
    label: s.subject_code,
    subject_id: s.subject_id,
    subject_name: s.subject_name,
    value: s.average_attendance ?? 0,
  }))
  const topSubjects = [...subjectAvg].sort((a, b) => b.value - a.value)
  const lowestSubjects = [...subjectAvg].sort((a, b) => a.value - b.value)
  const subjectCompareRows = subjectRows
    .filter((s) => s.previous_average_attendance !== null)
    .map((s) => ({
      label: s.subject_code,
      subject_id: s.subject_id,
      current: s.average_attendance ?? 0,
      previous: s.previous_average_attendance ?? 0,
    }))

  const trendRows = trends.data?.items ?? []
  const termTrendData = trendRows.map((t) => ({
    label: t.label,
    average_attendance: t.average_attendance ?? 0,
  }))
  const hasTrendHistory = trendRows.length > 1

  const bySubject = trends.data?.by_subject ?? []
  const bySubjectSeriesCodes = [...new Set(bySubject.map((b) => b.subject_code))]
  const bySubjectData = (() => {
    const map = new Map<string, Record<string, string | number>>()
    for (const item of bySubject) {
      const label = `Sem ${item.semester_no} · ${item.academic_year}`
      const row = map.get(label) ?? { label }
      row[item.subject_code] = item.average_attendance ?? 0
      map.set(label, row)
    }
    return [...map.values()]
  })()
  const hasSubjectTrendHistory = bySubjectData.length > 1
  const bySubjectSeries = bySubjectSeriesCodes.map((code, i) => ({
    key: code,
    label: code,
    color: `var(--chart-${(i % 5) + 1})`,
  }))

  const corrData = correlation.data
  const corrPoints = (corrData?.points ?? []).map((p) => ({
    x: p.attendance_percentage ?? 0,
    y: p.performance_percentage ?? 0,
  }))
  const hasCorrelation = corrPoints.length > 1

  return (
    <section id="attendance-charts" className="flex scroll-mt-6 flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Attendance charts</h2>
        <p className="text-sm text-muted-foreground">
          Distributions, subject comparisons, and trends over your enrollments in the current
          scope. Click a subject bar or heatmap cell to filter the student table.
        </p>
      </div>

      <div className="flex flex-col gap-5">
        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Distributions
          </h3>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <ChartCard
              title="Attendance distribution"
              subtitle="Students by attendance status"
              status={distError ? "error" : statusData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={GraduationCap}
              emptyTitle="No attendance records in this scope"
              emptyDescription="Attendance statuses will appear here once records are available for this scope."
              exportFileName={`faculty_attendance_${scope}_status_distribution.csv`}
              exportColumns={[
                { key: "label", label: "Status" },
                { key: "count", label: "Students" },
              ]}
              exportRows={statusData}
            >
              <SubjectBarChart
                data={statusData}
                xKey="label"
                dataKey="count"
                color="var(--chart-1)"
              />
            </ChartCard>

            <ChartCard
              title="Attendance histogram"
              subtitle="Students by attendance percentage band"
              status={distError ? "error" : bandData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="No attendance bands"
              emptyDescription="Attendance records will appear here once recorded for this scope."
              exportFileName={`faculty_attendance_${scope}_attendance_bands.csv`}
              exportColumns={[
                { key: "label", label: "Band" },
                { key: "count", label: "Students" },
              ]}
              exportRows={bandData}
            >
              <SubjectBarChart
                data={bandData}
                xKey="label"
                dataKey="count"
                color="var(--chart-3)"
                referenceLines={bandBoundaryLines(bandData, [
                  { value: thresholds.critical, label: `Critical ${thresholds.critical}%` },
                  { value: thresholds.compliance, label: `Baseline ${thresholds.compliance}%` },
                ])}
              />
            </ChartCard>

            <ChartCard
              title="Above vs below threshold"
              subtitle={`Split at the ${thresholds.compliance}% compliance baseline`}
              status={distError ? "error" : aboveBelowData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={Split}
              emptyTitle="No records in this scope"
              emptyDescription="The above/below split will appear here once attendance is recorded."
              exportFileName={`faculty_attendance_${scope}_above_below.csv`}
              exportColumns={[
                { key: "label", label: "Bucket" },
                { key: "count", label: "Students" },
              ]}
              exportRows={aboveBelowData}
            >
              <SubjectBarChart
                data={aboveBelowData}
                xKey="label"
                dataKey="count"
                bars={[
                  { dataKey: "count", name: "Students", color: "var(--chart-4)" },
                ]}
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Subject comparison
          </h3>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Subject-wise attendance"
              subtitle="Subject average attendance %"
              status={subjError ? "error" : subjectAvg.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={BarChart3}
              emptyTitle="No subjects in this scope"
              emptyDescription="Subjects you teach will appear here once enrollments are recorded."
              exportFileName={`faculty_attendance_${scope}_subject_attendance.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Avg %" },
              ]}
              exportRows={subjectAvg}
            >
              <SubjectBarChart
                data={subjectAvg}
                xKey="label"
                dataKey="value"
                color="var(--chart-1)"
                referenceLines={[baselineLine(thresholds.compliance)]}
                onBarClick={handleSubjectClick}
              />
            </ChartCard>

            <ChartCard
              title="Subject attendance comparison"
              subtitle="Current vs previous offering"
              status={subjError ? "error" : subjectCompareRows.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={GitCompareArrows}
              emptyTitle="No previous-term comparison"
              emptyDescription="Compare values appear when a subject was taught in an earlier term in this scope."
              exportFileName={`faculty_attendance_${scope}_subject_comparison.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "current", label: "Current %" },
                { key: "previous", label: "Previous %" },
              ]}
              exportRows={subjectCompareRows}
            >
              <SubjectBarChart
                data={subjectCompareRows}
                xKey="label"
                bars={[
                  { dataKey: "current", name: "Current", color: "var(--chart-1)" },
                  { dataKey: "previous", name: "Previous", color: "var(--chart-3)" },
                ]}
                referenceLines={[baselineLine(thresholds.compliance)]}
                onBarClick={handleSubjectClick}
              />
            </ChartCard>

            <ChartCard
              title="Top attendance subjects"
              subtitle="Highest average attendance first"
              status={subjError ? "error" : topSubjects.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={TrendingUp}
              emptyTitle="No subjects in this scope"
              emptyDescription="Subjects you teach will appear here once enrollments are recorded."
              exportFileName={`faculty_attendance_${scope}_top_subjects.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Avg %" },
              ]}
              exportRows={topSubjects}
            >
              <SubjectBarChart
                data={topSubjects}
                xKey="label"
                dataKey="value"
                color="var(--chart-2)"
                referenceLines={[baselineLine(thresholds.compliance)]}
                onBarClick={handleSubjectClick}
              />
            </ChartCard>

            <ChartCard
              title="Lowest attendance subjects"
              subtitle="Lowest average attendance first"
              status={subjError ? "error" : lowestSubjects.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={Target}
              emptyTitle="No subjects in this scope"
              emptyDescription="Subjects you teach will appear here once enrollments are recorded."
              exportFileName={`faculty_attendance_${scope}_lowest_subjects.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Avg %" },
              ]}
              exportRows={lowestSubjects}
            >
              <SubjectBarChart
                data={lowestSubjects}
                xKey="label"
                dataKey="value"
                color="var(--chart-5)"
                referenceLines={[baselineLine(thresholds.compliance)]}
                onBarClick={handleSubjectClick}
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Trends across terms
          </h3>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Semester attendance trend"
              subtitle="Term-over-term average attendance %"
              status={trendError ? "error" : hasTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={TrendingUp}
              emptyTitle="First term taught"
              emptyDescription="A term-over-term trend will appear once you have taught for more than one term."
              exportFileName={`faculty_attendance_${scope}_attendance_trend.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                { key: "average_attendance", label: "Avg %" },
              ]}
              exportRows={termTrendData}
            >
              <TrendChart
                data={termTrendData}
                xKey="label"
                series={[
                  { key: "average_attendance", label: "Avg attendance", color: "var(--chart-1)" },
                ]}
                yDomain={[0, 100]}
                yTickSuffix="%"
                referenceLines={[baselineLine(thresholds.compliance)]}
              />
            </ChartCard>

            <ChartCard
              title="Attendance trend by subject"
              subtitle="Per-subject average attendance across terms"
              status={trendError ? "error" : hasSubjectTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={BookOpen}
              emptyTitle="First term taught"
              emptyDescription="Per-subject trends will appear once subjects span more than one term."
              exportFileName={`faculty_attendance_${scope}_trend_by_subject.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                ...bySubjectSeriesCodes.map((code) => ({ key: code, label: code })),
              ]}
              exportRows={bySubjectData}
            >
              <TrendChart
                data={bySubjectData}
                xKey="label"
                series={bySubjectSeries}
                yDomain={[0, 100]}
                yTickSuffix="%"
                referenceLines={[baselineLine(thresholds.compliance)]}
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Attendance vs performance
          </h3>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Attendance vs performance correlation"
              subtitle={
                corrData && corrData.sample_size > 1
                  ? `Descriptive correlation · ${corrData.sample_size} students · r = ${corrData.pearson?.toFixed(2)} (${corrData.descriptor ?? "insufficient data"})`
                  : "Enrollment-level attendance % against performance %"
              }
              status={corrError ? "error" : hasCorrelation ? "ready" : "empty"}
              errorDescription={corrError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="Not enough paired records"
              emptyDescription="The scatter appears once enrollments have both attendance and performance records."
              exportFileName={`faculty_attendance_${scope}_correlation.csv`}
              exportColumns={[
                { key: "x", label: "Attendance %" },
                { key: "y", label: "Performance %" },
              ]}
              exportRows={corrPoints}
            >
              <ScatterChart
                data={corrPoints}
                referenceLines={[{ x: thresholds.compliance, label: `Baseline ${thresholds.compliance}%` }]}
              />
            </ChartCard>
          </div>
        </div>
      </div>
    </section>
  )
}
