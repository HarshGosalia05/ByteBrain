"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  BarChart3,
  BookOpen,
  Gauge,
  GitCompareArrows,
  Info,
  LayoutGrid,
  LineChart as LineChartIcon,
  Scale,
  Split,
  Target,
  TrendingUp,
} from "lucide-react"

import { SubjectBarChart, type ChartReferenceLine } from "@/components/shared/charts/bar-chart"
import { CapacityGauge } from "@/components/shared/charts/capacity-gauge"
import { ScatterChart } from "@/components/shared/charts/scatter-chart"
import { TrendChart } from "@/components/shared/charts/trend-chart"
import { ChartCard } from "@/components/shared/data/chart-card"
import { scopeStamp } from "@/lib/csv"
import type {
  WorkloadBenchmark,
  WorkloadCapacity,
  WorkloadForecast,
  WorkloadMatrices,
  WorkloadScatter,
  WorkloadSubjectBreakdown,
  WorkloadThresholds,
  WorkloadTrends,
} from "@/lib/faculty-api"
import type { SectionResult } from "@/lib/section-result"

import { WorkloadMatrixGrid, type WorkloadMatrixCellLike } from "./matrix-grid"

type ChartsViewProps = {
  subjectBreakdown: SectionResult<WorkloadSubjectBreakdown>
  trends: SectionResult<WorkloadTrends>
  capacity: SectionResult<WorkloadCapacity>
  matrices: SectionResult<WorkloadMatrices>
  scatter: SectionResult<WorkloadScatter>
  benchmark: SectionResult<WorkloadBenchmark>
  forecast: SectionResult<WorkloadForecast>
  thresholds: WorkloadThresholds
}

export function ChartsView({
  subjectBreakdown,
  trends,
  capacity,
  matrices,
  scatter,
  benchmark,
  forecast,
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

  const handleCellClick = (cell: WorkloadMatrixCellLike) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("subject_id", cell.subject_id)
    if (cell.metric === "classes") {
      if (cell.semester_no !== undefined) {
        params.set("semester", String(cell.semester_no))
      }
      if (cell.academic_year) {
        params.set("academic_year", cell.academic_year)
      }
    }
    params.set("page", "1")
    router.push(`${pathname}?${params.toString()}#students`)
  }

  const scope = scopeStamp([
    searchParams.get("academic_year"),
    searchParams.get("semester") ? `sem${searchParams.get("semester")}` : null,
    searchParams.get("subject_id"),
  ])

  const subjError = subjectBreakdown.error
  const trendError = trends.error
  const capacityError = capacity.error
  const matrixError = matrices.error
  const scatterError = scatter.error
  const benchmarkError = benchmark.error
  const forecastError = forecast.error

  const subjectItems = subjectBreakdown.data?.items ?? []
  const creditsData = subjectItems.map((s) => ({
    label: s.subject_code,
    subject_id: s.subject_id,
    subject_name: s.subject_name,
    value: s.credits ?? 0,
  }))
  const hoursData = subjectItems
    .filter((s) => (s.weekly_hours ?? 0) > 0)
    .map((s) => ({
      label: s.subject_code,
      subject_id: s.subject_id,
      subject_name: s.subject_name,
      value: s.weekly_hours ?? 0,
    }))
  const studentsData = subjectItems.map((s) => ({
    label: s.subject_code,
    subject_id: s.subject_id,
    subject_name: s.subject_name,
    value: s.students,
  }))
  const subjectMixData = (subjectBreakdown.data?.type_distribution ?? []).map((t) => ({
    label: t.label,
    count: t.count,
  }))
  const theoryPracticalData = (subjectBreakdown.data?.theory_practical ?? []).map((t) => ({
    label: t.label,
    value: t.credits ?? 0,
  }))
  const balanceCells = subjectBreakdown.data?.balance_matrix ?? []

  const capacityData = capacity.data
  const capacityLine: ChartReferenceLine = {
    y: thresholds.capacity_weekly_hours,
    label: `Capacity ${thresholds.capacity_weekly_hours}h`,
  }

  const trendRows = trends.data?.items ?? []
  const termTrendData = trendRows.map((t) => ({
    label: t.label,
    weekly_hours: t.weekly_hours,
  }))
  const hasTrendHistory = trendRows.length > 1

  const bySubject = trends.data?.by_subject ?? []
  const bySubjectSeriesCodes = [...new Set(bySubject.map((b) => b.subject_code))]
  const bySubjectData = (() => {
    const map = new Map<string, Record<string, string | number>>()
    for (const item of bySubject) {
      const label = `Sem ${item.semester_no} · ${item.academic_year}`
      const row = map.get(label) ?? { label }
      row[item.subject_code] = item.weekly_hours ?? 0
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

  const capacityTrendData = (trends.data?.capacity_trend ?? []).map((t) => ({
    label: t.label,
    weekly_hours: t.weekly_hours,
    capacity: t.capacity,
  }))
  const hasCapacityTrendHistory = capacityTrendData.length > 1

  const matricesData = matrices.data
  const scatterPoints = (scatter.data?.points ?? []).map((p) => ({
    x: p.students,
    y: p.credits ?? 0,
  }))
  const maxCredits = Math.max(1, ...(scatter.data?.points ?? []).map((p) => p.credits ?? 0))

  const benchmarkData = (benchmark.data?.items ?? []).map((b) => ({
    label: b.subject_code,
    subject_id: b.subject_id,
    value: b.weekly_hours ?? 0,
  }))
  const deptMean = benchmark.data?.department_mean_weekly_hours ?? null
  const deptMeanLine: ChartReferenceLine = deptMean
    ? { y: deptMean, label: `Dept mean ${deptMean}h` }
    : { y: 0, label: "Dept mean" }

  const forecastItems = forecast.data?.items ?? []
  const forecastData = forecastItems.map((f) => ({
    label: f.subject_code,
    subject_id: f.subject_id,
    value: f.expected_weekly_hours ?? 0,
  }))

  return (
    <section id="workload-charts" className="flex scroll-mt-6 flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Teaching workload charts</h2>
        <p className="text-sm text-muted-foreground">
          Derived hours, capacity, subject mix, trends, and matrices in the current scope. Click a
          subject bar or matrix cell to filter the student table.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Teaching load
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            <ChartCard
              title="Subject credit distribution"
              subtitle="Credits per subject offering"
              status={subjError ? "error" : creditsData.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={BarChart3}
              emptyTitle="No subjects in this scope"
              emptyDescription="Subjects you teach will appear here once enrollments are recorded."
              exportFileName={`faculty_workload_${scope}_subject_credits.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Credits" },
              ]}
              exportRows={creditsData}
            >
              <SubjectBarChart
                data={creditsData}
                xKey="label"
                dataKey="value"
                color="var(--chart-1)"
                onBarClick={handleSubjectClick}
              />
            </ChartCard>

            <ChartCard
              title="Weekly teaching load"
              subtitle={`Derived hours per subject (classes ÷ ${thresholds.weeks_per_semester} weeks)`}
              status={subjError ? "error" : hoursData.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="No subjects in this scope"
              emptyDescription="Derived weekly hours will appear here once attendance is recorded."
              exportFileName={`faculty_workload_${scope}_weekly_hours.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Weekly hours" },
              ]}
              exportRows={hoursData}
            >
              <SubjectBarChart
                data={hoursData}
                xKey="label"
                dataKey="value"
                color="var(--chart-2)"
                referenceLines={[capacityLine]}
                onBarClick={handleSubjectClick}
              />
            </ChartCard>

            <ChartCard
              title="Faculty capacity gauge"
              subtitle="Current weekly hours vs configured capacity"
              status={capacityError ? "error" : capacityData ? "ready" : "empty"}
              errorDescription={capacityError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="No capacity data"
              emptyDescription="Capacity utilization will appear here once teaching hours are recorded."
              exportFileName={`faculty_workload_${scope}_capacity.csv`}
              exportColumns={[
                { key: "actual_weekly_hours", label: "Actual hours" },
                { key: "capacity_weekly_hours", label: "Capacity hours" },
                { key: "utilization_pct", label: "Utilization %" },
                { key: "remaining_capacity", label: "Remaining hours" },
                { key: "band", label: "Band" },
              ]}
              exportRows={
                capacityData
                  ? [
                      {
                        actual_weekly_hours: capacityData.actual_weekly_hours,
                        capacity_weekly_hours: capacityData.capacity_weekly_hours,
                        utilization_pct: capacityData.utilization_pct,
                        remaining_capacity: capacityData.remaining_capacity,
                        band: capacityData.band,
                      },
                    ]
                  : []
              }
              className="xl:col-span-1"
            >
              {capacityData && (
                <CapacityGauge
                  utilizationPct={capacityData.utilization_pct}
                  actualWeeklyHours={capacityData.actual_weekly_hours}
                  capacityWeeklyHours={capacityData.capacity_weekly_hours}
                  remainingCapacity={capacityData.remaining_capacity}
                  overloadThreshold={thresholds.overload_threshold}
                  underutilizedThreshold={thresholds.underutilized_threshold}
                  band={capacityData.band}
                  reason={capacityData.reason}
                />
              )}
            </ChartCard>

            <ChartCard
              title="Student distribution per subject"
              subtitle="Distinct enrolled students per offering"
              status={subjError ? "error" : studentsData.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={BookOpen}
              emptyTitle="No subjects in this scope"
              emptyDescription="Student counts will appear here once enrollments are recorded."
              exportFileName={`faculty_workload_${scope}_student_distribution.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Students" },
              ]}
              exportRows={studentsData}
            >
              <SubjectBarChart
                data={studentsData}
                xKey="label"
                dataKey="value"
                color="var(--chart-4)"
                onBarClick={handleSubjectClick}
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Subject mix
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            <ChartCard
              title="Subject mix distribution"
              subtitle="Offerings by subject type"
              status={subjError ? "error" : subjectMixData.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={Split}
              emptyTitle="No subjects in this scope"
              emptyDescription="Subject types will appear here once enrollments are recorded."
              exportFileName={`faculty_workload_${scope}_subject_mix.csv`}
              exportColumns={[
                { key: "label", label: "Type" },
                { key: "count", label: "Offerings" },
              ]}
              exportRows={subjectMixData}
            >
              <SubjectBarChart
                data={subjectMixData}
                xKey="label"
                dataKey="count"
                color="var(--chart-3)"
              />
            </ChartCard>

            <ChartCard
              title="Theory vs practical distribution"
              subtitle="Credits by Theory and practical types"
              status={subjError ? "error" : theoryPracticalData.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={GitCompareArrows}
              emptyTitle="No practical subjects"
              emptyDescription="The theory/practical split appears once both types are recorded."
              exportFileName={`faculty_workload_${scope}_theory_practical.csv`}
              exportColumns={[
                { key: "label", label: "Type" },
                { key: "value", label: "Credits" },
              ]}
              exportRows={theoryPracticalData}
            >
              <SubjectBarChart
                data={theoryPracticalData}
                xKey="label"
                dataKey="value"
                color="var(--chart-2)"
              />
            </ChartCard>

            <ChartCard
              title="Credit vs student scatter"
              subtitle="Per-offering credits against enrolled students"
              status={scatterError ? "error" : scatterPoints.length > 1 ? "ready" : "empty"}
              errorDescription={scatterError ?? undefined}
              emptyIcon={Target}
              emptyTitle="Not enough offerings"
              emptyDescription="The scatter appears once two or more offerings exist in the scope."
              exportFileName={`faculty_workload_${scope}_credit_student.csv`}
              exportColumns={[
                { key: "x", label: "Students" },
                { key: "y", label: "Credits" },
              ]}
              exportRows={scatterPoints}
            >
              <ScatterChart
                data={scatterPoints}
                xLabel="Students"
                yLabel="Credits"
                xDomain={[0, "auto"]}
                yDomain={[0, Math.max(4, maxCredits)]}
                tooltipTitle="Credit vs student load"
                tooltipXLabel="Students"
                tooltipYLabel="Credits"
                valueSuffix=""
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
              title="Semester workload trend"
              subtitle="Term-over-term total weekly hours"
              status={trendError ? "error" : hasTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={TrendingUp}
              emptyTitle="First term taught"
              emptyDescription="A term-over-term trend will appear once you have taught for more than one term."
              exportFileName={`faculty_workload_${scope}_semester_trend.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                { key: "weekly_hours", label: "Weekly hours" },
              ]}
              exportRows={termTrendData}
            >
              <TrendChart
                data={termTrendData}
                xKey="label"
                series={[
                  { key: "weekly_hours", label: "Weekly hours", color: "var(--chart-1)" },
                ]}
                referenceLines={[{ y: thresholds.capacity_weekly_hours, label: `Capacity ${thresholds.capacity_weekly_hours}h` }]}
              />
            </ChartCard>

            <ChartCard
              title="Teaching hours timeline"
              subtitle="Per-subject weekly hours across terms"
              status={trendError ? "error" : hasSubjectTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={LineChartIcon}
              emptyTitle="First term taught"
              emptyDescription="Per-subject timelines will appear once subjects span more than one term."
              exportFileName={`faculty_workload_${scope}_hours_timeline.csv`}
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
                referenceLines={[{ y: thresholds.capacity_weekly_hours, label: `Capacity ${thresholds.capacity_weekly_hours}h` }]}
              />
            </ChartCard>

            <ChartCard
              title="Teaching capacity trend"
              subtitle="Actual weekly hours vs configured capacity"
              status={trendError ? "error" : hasCapacityTrendHistory ? "ready" : "empty"}
              errorDescription={trendError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="First term taught"
              emptyDescription="The capacity comparison will appear once more than one term exists."
              exportFileName={`faculty_workload_${scope}_capacity_trend.csv`}
              exportColumns={[
                { key: "label", label: "Term" },
                { key: "weekly_hours", label: "Actual hours" },
                { key: "capacity", label: "Capacity" },
              ]}
              exportRows={capacityTrendData}
            >
              <TrendChart
                data={capacityTrendData}
                xKey="label"
                series={[
                  { key: "weekly_hours", label: "Actual", color: "var(--chart-1)" },
                  { key: "capacity", label: "Capacity", color: "var(--chart-3)" },
                ]}
                referenceLines={[{ y: thresholds.capacity_weekly_hours, label: `Capacity ${thresholds.capacity_weekly_hours}h` }]}
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Workload matrices
          </h3>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Workload heatmap"
              subtitle="Classes conducted per subject and term"
              status={matrixError ? "error" : matricesData && matricesData.heatmap.length ? "ready" : "empty"}
              errorDescription={matrixError ?? undefined}
              emptyIcon={LayoutGrid}
              emptyTitle="No heatmap data"
              emptyDescription="Class counts will appear here once attendance is recorded for this scope."
              exportFileName={`faculty_workload_${scope}_heatmap.csv`}
              exportColumns={[
                { key: "subject_code", label: "Subject" },
                { key: "label", label: "Metric" },
                { key: "semester_no", label: "Semester" },
                { key: "academic_year", label: "Year" },
                { key: "value", label: "Classes" },
              ]}
              exportRows={(matricesData?.heatmap ?? []).map((c) => ({
                ...c,
                value: Math.round(c.value),
              }))}
            >
              <WorkloadMatrixGrid
                cells={matricesData?.heatmap ?? []}
                mode="heatmap"
                onCellClick={handleCellClick}
              />
            </ChartCard>

            <ChartCard
              title="Workload balance matrix"
              subtitle="Per-subject metrics normalized to the scope range"
              status={subjError ? "error" : balanceCells.length ? "ready" : "empty"}
              errorDescription={subjError ?? undefined}
              emptyIcon={Scale}
              emptyTitle="No subjects in this scope"
              emptyDescription="Balance cells will appear here once more than one subject exists."
              exportFileName={`faculty_workload_${scope}_balance_matrix.csv`}
              exportColumns={[
                { key: "subject_code", label: "Subject" },
                { key: "label", label: "Metric" },
                { key: "value", label: "Value" },
                { key: "normalized", label: "Normalized" },
              ]}
              exportRows={balanceCells}
            >
              <WorkloadMatrixGrid cells={balanceCells} mode="balance" onCellClick={handleCellClick} />
            </ChartCard>

            <ChartCard
              title="Resource utilization matrix"
              subtitle="Capacity, balance contribution, and coverage per subject"
              status={matrixError ? "error" : matricesData && matricesData.utilization.length ? "ready" : "empty"}
              errorDescription={matrixError ?? undefined}
              emptyIcon={Gauge}
              emptyTitle="No subjects in this scope"
              emptyDescription="Utilization cells will appear here once offerings are recorded."
              exportFileName={`faculty_workload_${scope}_utilization_matrix.csv`}
              exportColumns={[
                { key: "subject_code", label: "Subject" },
                { key: "label", label: "Dimension" },
                { key: "value", label: "Value" },
              ]}
              exportRows={(matricesData?.utilization ?? []).map((c) => ({
                subject_code: c.subject_code,
                label: c.label,
                value: c.value,
              }))}
            >
              <WorkloadMatrixGrid
                cells={matricesData?.utilization ?? []}
                mode="utilization"
                onCellClick={handleCellClick}
              />
            </ChartCard>

            <ChartCard
              title="Resource allocation matrix"
              subtitle="Share of scope credits, students, and hours per subject"
              status={matrixError ? "error" : matricesData && matricesData.allocation.length ? "ready" : "empty"}
              errorDescription={matrixError ?? undefined}
              emptyIcon={Split}
              emptyTitle="No subjects in this scope"
              emptyDescription="Allocation shares will appear here once offerings are recorded."
              exportFileName={`faculty_workload_${scope}_allocation_matrix.csv`}
              exportColumns={[
                { key: "subject_code", label: "Subject" },
                { key: "label", label: "Resource" },
                { key: "value", label: "Share %" },
              ]}
              exportRows={(matricesData?.allocation ?? []).map((c) => ({
                subject_code: c.subject_code,
                label: c.label,
                value: c.value,
              }))}
            >
              <WorkloadMatrixGrid
                cells={matricesData?.allocation ?? []}
                mode="allocation"
                onCellClick={handleCellClick}
              />
            </ChartCard>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
            Benchmark &amp; next-term projection
          </h3>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Department benchmark position"
              subtitle="Your offerings vs the department aggregate (no individual faculty data)"
              status={benchmarkError ? "error" : benchmarkData.length ? "ready" : "empty"}
              errorDescription={benchmarkError ?? undefined}
              emptyIcon={BarChart3}
              emptyTitle="No subjects in this scope"
              emptyDescription="Your position will appear here once offerings are recorded."
              exportFileName={`faculty_workload_${scope}_benchmark.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Weekly hours" },
              ]}
              exportRows={benchmarkData}
            >
              <SubjectBarChart
                data={benchmarkData}
                xKey="label"
                dataKey="value"
                color="var(--chart-1)"
                referenceLines={[deptMeanLine]}
                onBarClick={handleSubjectClick}
              />
            </ChartCard>

            <ChartCard
              title="Expected teaching load (next term)"
              subtitle="Rule-based projection from prior offerings"
              status={forecastError ? "error" : forecastData.length ? "ready" : "empty"}
              errorDescription={forecastError ?? undefined}
              emptyIcon={TrendingUp}
              emptyTitle="No prior offering history to project from"
              emptyDescription="The projection appears once you have taught a subject in a previous term."
              exportFileName={`faculty_workload_${scope}_expected_load.csv`}
              exportColumns={[
                { key: "label", label: "Subject" },
                { key: "value", label: "Expected weekly hours" },
              ]}
              exportRows={forecastData}
            >
              <SubjectBarChart
                data={forecastData}
                xKey="label"
                dataKey="value"
                color="var(--chart-2)"
                onBarClick={handleSubjectClick}
              />
              {forecast.data && forecast.data.source_reason && (
                <p className="mt-3 flex items-start gap-1.5 text-xs text-muted-foreground">
                  <Info className="mt-0.5 size-3.5 shrink-0" />
                  {forecast.data.source_reason}
                  {forecast.data.expected_total_weekly_hours !== null && (
                    <>
                      {" "}
                      Projected total {forecast.data.expected_total_weekly_hours}h ·{" "}
                      {forecast.data.remaining_capacity !== null
                        ? `${forecast.data.remaining_capacity}h remaining`
                        : "no remaining capacity estimate"}
                      .
                    </>
                  )}
                </p>
              )}
            </ChartCard>
          </div>
        </div>
      </div>
    </section>
  )
}
