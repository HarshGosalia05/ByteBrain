"use client"

import { useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  Award,
  BarChart3,
  BookOpen,
  CalendarCheck,
  Gauge,
  GraduationCap,
  Repeat,
  Search,
  TrendingUp,
  Users,
  X,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { SubjectBarChart, type ChartReferenceLine } from "@/components/shared/charts/bar-chart"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { ChartCard } from "@/components/shared/data/chart-card"
import { scopeStamp } from "@/lib/csv"
import { cn } from "@/lib/utils"
import type {
  PerformanceDistributions,
  PerformanceSubjectBreakdown,
  PerformanceThresholds,
  PerformanceTrends,
} from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"

type ChartsViewProps = {
  distributions: SectionResult<PerformanceDistributions>
  subjectBreakdown: SectionResult<PerformanceSubjectBreakdown>
  trends: SectionResult<PerformanceTrends>
  thresholds: PerformanceThresholds
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

function thresholdBandLine(
  bands: Array<{ label: string; count: number }>,
  threshold: number,
): ChartReferenceLine[] {
  let boundary: string | undefined
  for (const band of bands) {
    const upper = parseBandUpperBound(band.label)
    if (upper === null) continue
    if (upper <= threshold) boundary = band.label
  }
  if (!boundary) return []
  return [{ x: boundary, position: "end", label: `Baseline ${threshold}%` }]
}

const selectClassName =
  "h-9 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 w-full sm:w-auto"

export function ChartsView({
  distributions,
  subjectBreakdown,
  trends,
  thresholds,
}: ChartsViewProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const [searchQuery, setSearchQuery] = useState("")
  const [selectedSemester, setSelectedSemester] = useState("")
  const [selectedSubject, setSelectedSubject] = useState("")

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

  const distData = distributions.data
  const gradeData = (distData?.grade_distribution ?? []).map((g) => ({
    grade: g.grade,
    count: g.count,
  }))
  const perfBandData = (distData?.performance_bands ?? []).map((b) => ({
    label: b.label,
    count: b.count,
  }))
  const attBandData = (distData?.attendance_bands ?? []).map((b) => ({
    label: b.label,
    count: b.count,
  }))
  const attemptData = (distData?.attempt_analysis ?? []).map((a) => ({
    attempt: a.attempt,
    pass_count: a.pass_count,
    fail_count: a.fail_count,
  }))
  const categoryData = (distData?.category_distribution ?? []).map((c) => ({
    label: c.label,
    count: c.count,
  }))

  const subjectRows = useMemo(() => subjectBreakdown.data?.items ?? [], [subjectBreakdown.data])

  const uniqueSemesters = useMemo(() => {
    const sems = new Set<number>()
    for (const s of subjectRows) sems.add(s.semester_no)
    return Array.from(sems).sort((a, b) => a - b)
  }, [subjectRows])

  const uniqueSubjects = useMemo(() => {
    const map = new Map<string, { subject_id: string; subject_code: string; subject_name: string }>()
    for (const s of subjectRows) {
      if (!map.has(s.subject_id)) {
        map.set(s.subject_id, { subject_id: s.subject_id, subject_code: s.subject_code, subject_name: s.subject_name })
      }
    }
    return Array.from(map.values()).sort((a, b) => a.subject_code.localeCompare(b.subject_code))
  }, [subjectRows])

  const filteredSubjectRows = useMemo(() => {
    let rows = subjectRows
    if (selectedSemester) {
      rows = rows.filter((s) => String(s.semester_no) === selectedSemester)
    }
    if (selectedSubject) {
      rows = rows.filter((s) => s.subject_id === selectedSubject)
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase()
      rows = rows.filter(
        (s) =>
          s.subject_code.toLowerCase().includes(q) ||
          s.subject_name.toLowerCase().includes(q),
      )
    }
    return rows
  }, [subjectRows, selectedSemester, selectedSubject, searchQuery])

  const hasSubjectFilters = Boolean(selectedSemester || selectedSubject || searchQuery.trim())

  const subjectChart = (valueKey: "average_performance" | "average_attendance" | "pass_percentage" | "enrollments") =>
    filteredSubjectRows.map((s) => ({
      label: s.subject_code,
      subject_id: s.subject_id,
      subject_name: s.subject_name,
      value: (s[valueKey] as number | null) ?? 0,
    }))

  const trendRows = trends.data?.items ?? []
  const trendDataFor = (key: "average_performance" | "average_attendance" | "pass_percentage") =>
    trendRows.map((t) => ({ label: t.label, [key]: t[key] ?? 0 }))
  const hasTrendHistory = trendRows.length > 1

  return (
    <section id="performance-charts" className="flex scroll-mt-6 flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Distributions &amp; comparisons</h2>
        <p className="text-sm text-muted-foreground">
          Twelve views over your enrollments in the current scope. Click a subject bar to filter the
          student table.
        </p>
      </div>

      <div className="flex flex-col gap-5">
        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Distributions
          </h3>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <ChartCard
              title="Grade distribution"
              subtitle="Students by grade (O … F)"
              status={distError ? "error" : gradeData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={GraduationCap}
              emptyTitle="No grades in this scope"
              emptyDescription="Grades will appear here once performance records are recorded for this scope."
              exportFileName={`faculty_performance_${scope}_grades.csv`}
              exportColumns={[
                { key: "grade", label: "Grade" },
                { key: "count", label: "Students" },
              ]}
              exportRows={gradeData}
            >
              <SubjectBarChart data={gradeData} xKey="grade" dataKey="count" color="var(--chart-1)" />
            </ChartCard>

            <ChartCard
              title="Performance bands"
              subtitle="Students by percentage band"
              status={distError ? "error" : perfBandData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="No performance bands"
              emptyDescription="Performance records will appear here once recorded for this scope."
              exportFileName={`faculty_performance_${scope}_performance_bands.csv`}
              exportColumns={[
                { key: "label", label: "Band" },
                { key: "count", label: "Students" },
              ]}
              exportRows={perfBandData}
            >
              <SubjectBarChart
                data={perfBandData}
                xKey="label"
                dataKey="count"
                color="var(--chart-2)"
                referenceLines={thresholdBandLine(perfBandData, thresholds.performance)}
              />
            </ChartCard>

            <ChartCard
              title="Attendance bands"
              subtitle="Students by attendance percentage"
              status={distError ? "error" : attBandData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={CalendarCheck}
              emptyTitle="No attendance bands"
              emptyDescription="Attendance records will appear here once recorded for this scope."
              exportFileName={`faculty_performance_${scope}_attendance_bands.csv`}
              exportColumns={[
                { key: "label", label: "Band" },
                { key: "count", label: "Students" },
              ]}
              exportRows={attBandData}
            >
              <SubjectBarChart
                data={attBandData}
                xKey="label"
                dataKey="count"
                color="var(--chart-3)"
                referenceLines={thresholdBandLine(attBandData, thresholds.attendance)}
              />
            </ChartCard>

            <ChartCard
              title="Attempt vs result"
              subtitle="Pass / fail count by attempt"
              status={distError ? "error" : attemptData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={Repeat}
              emptyTitle="No attempt data"
              emptyDescription="Repeat-attempt records are not yet available for this scope."
              exportFileName={`faculty_performance_${scope}_attempts.csv`}
              exportColumns={[
                { key: "attempt", label: "Attempt" },
                { key: "pass_count", label: "Pass" },
                { key: "fail_count", label: "Fail" },
              ]}
              exportRows={attemptData}
            >
              <SubjectBarChart
                data={attemptData}
                xKey="attempt"
                bars={[
                  { dataKey: "pass_count", name: "Pass", color: "var(--chart-2)" },
                  { dataKey: "fail_count", name: "Fail", color: "var(--chart-5)" },
                ]}
              />
            </ChartCard>

            <ChartCard
              title="Category distribution"
              subtitle="Students by performance category"
              status={distError ? "error" : categoryData.length ? "ready" : "empty"}
              errorDescription={distError ?? undefined}
              emptyIcon={Award}
              emptyTitle="No category data"
              emptyDescription="Performance categories will appear here once recorded for this scope."
              exportFileName={`faculty_performance_${scope}_categories.csv`}
              exportColumns={[
                { key: "label", label: "Category" },
                { key: "count", label: "Students" },
              ]}
              exportRows={categoryData}
            >
              <SubjectBarChart
                data={categoryData}
                xKey="label"
                dataKey="count"
                color="var(--chart-4)"
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Subject comparison
          </h3>
          <div className="mb-4 flex flex-col gap-3 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:gap-3">
            <div className="relative flex-1 sm:max-w-[240px]">
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search subjects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 pl-8 text-sm"
              />
            </div>
            <select
              className={selectClassName}
              value={selectedSemester}
              onChange={(e) => setSelectedSemester(e.target.value)}
              aria-label="Filter by semester"
            >
              <option value="">All Semesters</option>
              {uniqueSemesters.map((s) => (
                <option key={s} value={String(s)}>
                  Semester {s}
                </option>
              ))}
            </select>
            <select
              className={cn(selectClassName, "sm:max-w-[220px]")}
              value={selectedSubject}
              onChange={(e) => setSelectedSubject(e.target.value)}
              aria-label="Filter by subject"
            >
              <option value="">All Subjects</option>
              {uniqueSubjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.subject_code} - {s.subject_name}
                </option>
              ))}
            </select>
            {hasSubjectFilters && (
              <button
                onClick={() => {
                  setSearchQuery("")
                  setSelectedSemester("")
                  setSelectedSubject("")
                }}
                className="flex h-9 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <X className="size-3.5" />
                Clear
              </button>
            )}
          </div>
          {hasSubjectFilters && (
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Filters:</span>
              {selectedSemester && (
                <Badge variant="secondary" className="gap-1">
                  Semester {selectedSemester}
                  <button onClick={() => setSelectedSemester("")} className="ml-0.5 hover:text-foreground">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {selectedSubject && (
                <Badge variant="secondary" className="gap-1">
                  {uniqueSubjects.find((s) => s.subject_id === selectedSubject)?.subject_code ?? selectedSubject}
                  <button onClick={() => setSelectedSubject("")} className="ml-0.5 hover:text-foreground">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {searchQuery.trim() && (
                <Badge variant="secondary" className="gap-1">
                  Search: &quot;{searchQuery.trim()}&quot;
                  <button onClick={() => setSearchQuery("")} className="ml-0.5 hover:text-foreground">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
            </div>
          )}
          <div className="flex flex-col gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <ChartCard
                title="Average performance by subject"
                subtitle="Subject average percentage"
                status={subjError ? "error" : filteredSubjectRows.length ? "ready" : "empty"}
                errorDescription={subjError ?? undefined}
                emptyIcon={Gauge}
                emptyTitle="No subjects in this scope"
                emptyDescription={hasSubjectFilters ? "Try adjusting your filters." : "Subjects you teach will appear here once enrollments are recorded."}
                exportFileName={`faculty_performance_${scope}_subject_performance.csv`}
                exportColumns={[
                  { key: "label", label: "Subject" },
                  { key: "value", label: "Avg %" },
                ]}
                exportRows={subjectChart("average_performance")}
              >
                <SubjectBarChart
                  data={subjectChart("average_performance")}
                  xKey="label"
                  dataKey="value"
                  color="var(--chart-1)"
                  onBarClick={handleSubjectClick}
                  height={320}
                />
              </ChartCard>

              <ChartCard
                title="Average attendance by subject"
                subtitle="Subject average attendance %"
                status={subjError ? "error" : filteredSubjectRows.length ? "ready" : "empty"}
                errorDescription={subjError ?? undefined}
                emptyIcon={CalendarCheck}
                emptyTitle="No subjects in this scope"
                emptyDescription={hasSubjectFilters ? "Try adjusting your filters." : "Subjects you teach will appear here once enrollments are recorded."}
                exportFileName={`faculty_performance_${scope}_subject_attendance.csv`}
                exportColumns={[
                  { key: "label", label: "Subject" },
                  { key: "value", label: "Avg %" },
                ]}
                exportRows={subjectChart("average_attendance")}
              >
                <SubjectBarChart
                  data={subjectChart("average_attendance")}
                  xKey="label"
                  dataKey="value"
                  color="var(--chart-2)"
                  onBarClick={handleSubjectClick}
                  height={320}
                />
              </ChartCard>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <ChartCard
                title="Pass rate by subject"
                subtitle="Subject pass percentage"
                status={subjError ? "error" : filteredSubjectRows.length ? "ready" : "empty"}
                errorDescription={subjError ?? undefined}
                emptyIcon={BookOpen}
                emptyTitle="No subjects in this scope"
                emptyDescription={hasSubjectFilters ? "Try adjusting your filters." : "Subjects you teach will appear here once enrollments are recorded."}
                exportFileName={`faculty_performance_${scope}_subject_pass_rate.csv`}
                exportColumns={[
                  { key: "label", label: "Subject" },
                  { key: "value", label: "Pass %" },
                ]}
                exportRows={subjectChart("pass_percentage")}
              >
                <SubjectBarChart
                  data={subjectChart("pass_percentage")}
                  xKey="label"
                  dataKey="value"
                  color="var(--chart-3)"
                  onBarClick={handleSubjectClick}
                  height={320}
                />
              </ChartCard>

              <ChartCard
                title="Enrollment by subject"
                subtitle="Students per subject"
                status={subjError ? "error" : filteredSubjectRows.length ? "ready" : "empty"}
                errorDescription={subjError ?? undefined}
                emptyIcon={Users}
                emptyTitle="No subjects in this scope"
                emptyDescription={hasSubjectFilters ? "Try adjusting your filters." : "Subjects you teach will appear here once enrollments are recorded."}
                exportFileName={`faculty_performance_${scope}_subject_enrollments.csv`}
                exportColumns={[
                  { key: "label", label: "Subject" },
                  { key: "value", label: "Students" },
                ]}
                exportRows={subjectChart("enrollments")}
              >
                <SubjectBarChart
                  data={subjectChart("enrollments")}
                  xKey="label"
                  dataKey="value"
                  color="var(--chart-4)"
                  onBarClick={handleSubjectClick}
                  height={320}
                />
              </ChartCard>
            </div>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Trends across terms
          </h3>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <ChartCard
              title="Average performance trend"
              subtitle="Term-over-term average percentage"
              status={trendError ? "error" : hasTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={TrendingUp}
              emptyTitle="First term taught"
              emptyDescription="A term-over-term trend will appear once you have taught for more than one term."
              exportFileName={`faculty_performance_${scope}_performance_trend.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                { key: "average_performance", label: "Avg %" },
              ]}
              exportRows={trendDataFor("average_performance")}
            >
              <TrendChart
                data={trendDataFor("average_performance")}
                xKey="label"
                series={[
                  { key: "average_performance", label: "Avg performance", color: "var(--chart-1)" },
                ]}
                yDomain={[0, 100]}
                yTickSuffix="%"
                referenceLines={[baselineLine(thresholds.performance)]}
              />
            </ChartCard>

            <ChartCard
              title="Average attendance trend"
              subtitle="Term-over-term average attendance %"
              status={trendError ? "error" : hasTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={TrendingUp}
              emptyTitle="First term taught"
              emptyDescription="A term-over-term trend will appear once you have taught for more than one term."
              exportFileName={`faculty_performance_${scope}_attendance_trend.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                { key: "average_attendance", label: "Avg %" },
              ]}
              exportRows={trendDataFor("average_attendance")}
            >
              <TrendChart
                data={trendDataFor("average_attendance")}
                xKey="label"
                series={[
                  { key: "average_attendance", label: "Avg attendance", color: "var(--chart-2)" },
                ]}
                yDomain={[0, 100]}
                yTickSuffix="%"
                referenceLines={[baselineLine(thresholds.attendance)]}
              />
            </ChartCard>

            <ChartCard
              title="Pass rate trend"
              subtitle="Term-over-term pass percentage"
              status={trendError ? "error" : hasTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={BarChart3}
              emptyTitle="First term taught"
              emptyDescription="A term-over-term trend will appear once you have taught for more than one term."
              exportFileName={`faculty_performance_${scope}_pass_rate_trend.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                { key: "pass_percentage", label: "Pass %" },
              ]}
              exportRows={trendDataFor("pass_percentage")}
            >
              <TrendChart
                data={trendDataFor("pass_percentage")}
                xKey="label"
                series={[
                  { key: "pass_percentage", label: "Pass rate", color: "var(--chart-3)" },
                ]}
                yDomain={[0, 100]}
                yTickSuffix="%"
                referenceLines={[baselineLine(thresholds.pass_rate_healthy)]}
              />
            </ChartCard>
          </div>
        </div>
      </div>
    </section>
  )
}
