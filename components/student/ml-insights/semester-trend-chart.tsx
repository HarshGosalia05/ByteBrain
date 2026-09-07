"use client"

import * as React from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { cn } from "@/lib/utils"
import {
  m1V3GradeFromPercentage,
  m1V3GradePoint,
  m1V3PredictedPercentage,
  m1V3PredictedSGPA,
  type M1V3SubjectPrediction,
} from "@/lib/m1v3-prediction"
import { ChartContainer } from "@/components/shared/charts/chart-container"
import { ChartCard } from "@/components/shared/data/chart-card"

type Metric = "sgpa" | "percentage"

type ChartPoint = {
  label: string
  sgpa: number | null
  percentage: number | null
  isPredicted: boolean
  semesterNo: number | null
  /** Subject marks for tooltip (only for AI-predicted bars) */
  subjectMarks?: {
    name: string
    marks: number
  }[]
}

type TooltipPayloadItem = {
  name?: string
  value?: number | string
  color?: string
  payload?: ChartPoint
}

function MetricToggle({
  metric,
  onChange,
}: {
  metric: Metric
  onChange: (m: Metric) => void
}) {
  return (
    <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
      <button
        type="button"
        className={cn(
          "h-8 rounded px-2.5 text-sm font-medium transition-colors",
          metric === "sgpa"
            ? "bg-muted text-foreground"
            : "text-muted-foreground hover:text-foreground",
        )}
        onClick={() => onChange("sgpa")}
        aria-pressed={metric === "sgpa"}
      >
        SGPA
      </button>
      <button
        type="button"
        className={cn(
          "h-8 rounded px-2.5 text-sm font-medium transition-colors",
          metric === "percentage"
            ? "bg-muted text-foreground"
            : "text-muted-foreground hover:text-foreground",
        )}
        onClick={() => onChange("percentage")}
        aria-pressed={metric === "percentage"}
      >
        %
      </button>
    </div>
  )
}

function ChartTooltip({
  active,
  payload,
  label,
  metric,
}: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string | number
  metric: Metric
}) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload as ChartPoint | undefined
  const val = payload[0]?.value as number | undefined

  return (
    <div className="min-w-60 max-w-sm rounded-lg border border-border bg-popover/95 p-3 text-xs shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-foreground">{label}</p>
        {point?.isPredicted && (
          <span className="text-[0.65rem] text-muted-foreground">
            AI predicted
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between gap-4">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <span
            className="size-2 shrink-0 rounded-full"
            style={{ backgroundColor: payload[0]?.color }}
          />
          {metric === "sgpa" ? "SGPA" : "Percentage"}
        </span>
        <span className="font-semibold tabular-nums text-foreground">
          {metric === "sgpa"
            ? (val as number)?.toFixed(2)
            : `${(val as number)?.toFixed(1)}%`}
        </span>
      </div>

      {/* Normal visible list of all subjects with marks (no grade, no scrollbar) */}
      {point?.isPredicted && point.subjectMarks && point.subjectMarks.length > 0 && (
        <div className="mt-2.5 border-t border-border pt-2">
          <p className="mb-1.5 text-[0.68rem] font-medium text-muted-foreground">
            Subject Marks (/70)
          </p>
          <div className="flex flex-col gap-1.5">
            {point.subjectMarks.map((s, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 text-xs"
              >
                <span className="text-muted-foreground">{s.name}</span>
                <span className="font-semibold tabular-nums text-foreground">
                  {s.marks.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Custom label rendered on top of each bar showing the SGPA / percentage value.
function BarTopLabel({
  x,
  y,
  width,
  value,
  metric,
}: {
  x?: number
  y?: number
  width?: number
  value?: number | string | null
  metric: Metric
}) {
  if (value == null || value === "") return null
  const numVal = typeof value === "string" ? parseFloat(value) : value
  if (isNaN(numVal as number)) return null
  const text =
    metric === "sgpa"
      ? (numVal as number).toFixed(2)
      : `${(numVal as number).toFixed(1)}%`
  return (
    <text
      x={(x ?? 0) + (width ?? 0) / 2}
      y={(y ?? 0) - 5}
      textAnchor="middle"
      fontSize={10}
      fontWeight={600}
      fill="var(--foreground)"
      style={{ pointerEvents: "none" }}
    >
      {text}
    </text>
  )
}

// ---- SGPA computation from M1V3 subjects --------------------------------

function buildPredictedSGPAPoint(
  subjects: M1V3SubjectPrediction[],
  semesterNo: number | null,
  label: string,
): ChartPoint {
  const sgpa = m1V3PredictedSGPA(subjects)
  const pct = m1V3PredictedPercentage(subjects)

  const subjectMarks = subjects.map((s, i) => ({
    name: s.subject_name || `Subject ${i + 1}`,
    marks: s.predicted_end_sem_marks,
  }))

  return {
    label,
    sgpa,
    percentage: pct,
    isPredicted: true,
    semesterNo,
    subjectMarks,
  }
}

// Fallback: marks-only path (when full M1V3 subject objects are not present).
function buildFallbackSGPAPoint(
  predictedMarks: number[],
  semesterNo: number | null,
  label: string,
): ChartPoint {
  if (predictedMarks.length === 0)
    return { label, sgpa: null, percentage: null, isPredicted: true, semesterNo }

  let totalGP = 0
  let totalPct = 0
  const subjectMarks: { name: string; marks: number }[] = []

  for (let i = 0; i < predictedMarks.length; i++) {
    const mark = predictedMarks[i]
    const pct = Math.min(100, Math.max(0, (mark / 70) * 100))
    const grade = m1V3GradeFromPercentage(pct)
    const gp = m1V3GradePoint(grade)
    totalGP += gp
    totalPct += pct
    subjectMarks.push({
      name: `Subject ${i + 1}`,
      marks: mark,
    })
  }
  const avgGP = Number((totalGP / predictedMarks.length).toFixed(2))
  const avgPct = Number((totalPct / predictedMarks.length).toFixed(1))
  return {
    label,
    sgpa: avgGP,
    percentage: avgPct,
    isPredicted: true,
    semesterNo,
    subjectMarks,
  }
}

// -------------------------------------------------------------------------

export function SemesterTrendChart({
  history,
  predictedNextSemester,
  currentSemester,
}: {
  history: Array<{
    semester_no: number
    semester_sgpa: number | null
    semester_percentage: number | null
  }>
  predictedNextSemester: {
    sgpa: number | null
    percentage: number | null
    semester_no: number | null
  } | null
  currentSemester: {
    semester_no: number | null
    subjects?: M1V3SubjectPrediction[] | null
    predictedMarks: number[]
  } | null
}) {
  const [metric, setMetric] = React.useState<Metric>("sgpa")
  const uid = React.useId()

  const currentSemNo = currentSemester?.semester_no ?? null

  const actualPoints = history
    .filter(
      (p) =>
        ((p.semester_sgpa !== null && p.semester_sgpa > 0) ||
          (p.semester_percentage !== null && p.semester_percentage > 0)) &&
        (currentSemNo === null || p.semester_no !== currentSemNo),
    )
    .map((p) => ({
      label: `Sem ${p.semester_no}`,
      sgpa: p.semester_sgpa,
      percentage: p.semester_percentage,
      isPredicted: false,
      semesterNo: p.semester_no,
    }))

  // Current semester AI point — uses proper SGPA formula when M1V3 subjects
  // with credits are available; falls back to linear approximation otherwise.
  const currentSemPoint: ChartPoint | null = (() => {
    if (!currentSemester) return null
    const semLabel = currentSemester.semester_no
      ? `Sem ${currentSemester.semester_no} (AI)`
      : "Current Sem (AI)"

    if (
      currentSemester.subjects &&
      currentSemester.subjects.length > 0
    ) {
      const point = buildPredictedSGPAPoint(
        currentSemester.subjects,
        currentSemester.semester_no,
        semLabel,
      )
      // Only show this point if we got a non-null value
      if (point.sgpa !== null || point.percentage !== null) return point
    }

    if (currentSemester.predictedMarks.length > 0) {
      return buildFallbackSGPAPoint(
        currentSemester.predictedMarks,
        currentSemester.semester_no,
        semLabel,
      )
    }
    return null
  })()

  const predictedPoint: ChartPoint | null =
    predictedNextSemester &&
    (predictedNextSemester.sgpa !== null ||
      predictedNextSemester.percentage !== null) &&
    (currentSemester === null ||
      predictedNextSemester.semester_no !== currentSemester.semester_no)
      ? {
          label: predictedNextSemester.semester_no
            ? `Sem ${predictedNextSemester.semester_no} (AI)`
            : "AI Predicted",
          sgpa: predictedNextSemester.sgpa,
          percentage: predictedNextSemester.percentage,
          isPredicted: true,
          semesterNo: predictedNextSemester.semester_no,
        }
      : null

  const allPoints: ChartPoint[] = [...actualPoints]
  if (currentSemPoint) allPoints.push(currentSemPoint)
  if (predictedPoint) allPoints.push(predictedPoint)
  const data: ChartPoint[] = allPoints.sort((a, b) => {
    const na = a.semesterNo ?? Number.POSITIVE_INFINITY
    const nb = b.semesterNo ?? Number.POSITIVE_INFINITY
    return na - nb
  })

  const hasAny = data.length > 0
  const yDomain: [number, number] = metric === "sgpa" ? [0, 10] : [0, 100]

  const actualColor = "var(--chart-2)"
  const predictedColor = "var(--chart-1)"

  return (
    <ChartCard
      title="Semester performance trend"
      subtitle="SGPA / percentage across completed semesters (Sem 1–6 actual) with AI predicted SGPA for upcoming semesters."
      status={hasAny ? "ready" : "empty"}
      emptyTitle="No trend data"
      emptyDescription="There is no semester performance data available to chart yet."
    >
      {hasAny && (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: actualColor }}
                />
                Completed semester
              </span>
              {currentSemPoint && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span
                    className="size-2 shrink-0 rounded-full"
                    style={{ backgroundColor: predictedColor }}
                  />
                  AI predicted (current semester)
                </span>
              )}
              {predictedPoint && !currentSemPoint && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span
                    className="size-2 shrink-0 rounded-full"
                    style={{ backgroundColor: predictedColor }}
                  />
                  AI predicted (next semester)
                </span>
              )}
              {predictedPoint && currentSemPoint && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span
                    className="size-2 shrink-0 rounded-full"
                    style={{ backgroundColor: predictedColor }}
                  />
                  AI predicted
                </span>
              )}
            </div>
            <MetricToggle metric={metric} onChange={setMetric} />
          </div>

          <ChartContainer height={280}>
            <BarChart
              data={data}
              margin={{ top: 22, right: 16, bottom: 8, left: 0 }}
              barCategoryGap="24%"
            >
              <defs>
                <linearGradient
                  id={`${uid}-actual`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={actualColor} stopOpacity={0.9} />
                  <stop
                    offset="100%"
                    stopColor={actualColor}
                    stopOpacity={0.5}
                  />
                </linearGradient>
                <linearGradient
                  id={`${uid}-predicted`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor={predictedColor}
                    stopOpacity={0.9}
                  />
                  <stop
                    offset="100%"
                    stopColor={predictedColor}
                    stopOpacity={0.55}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                stroke="var(--border)"
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                stroke="var(--muted-foreground)"
                tickMargin={10}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                stroke="var(--muted-foreground)"
                width={44}
                tickMargin={6}
                domain={yDomain}
                tickFormatter={(v: number) =>
                  metric === "sgpa" ? v.toFixed(1) : `${v}%`
                }
              />
              <Tooltip
                content={
                  <ChartTooltip
                    metric={metric}
                    active={undefined}
                    payload={undefined}
                    label={undefined}
                  />
                }
                cursor={{ fill: "var(--muted)", opacity: 0.4 }}
                wrapperStyle={{ outline: "none" }}
              />
              <ReferenceLine
                y={metric === "sgpa" ? 7 : 70}
                stroke="var(--muted-foreground)"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: "Target",
                  fontSize: 10,
                  fill: "var(--muted-foreground)",
                  position: "insideTopLeft",
                }}
              />
              <Bar
                dataKey={metric}
                name={metric === "sgpa" ? "SGPA" : "Percentage"}
                radius={[6, 6, 2, 2]}
                maxBarSize={52}
                isAnimationActive
                animationDuration={600}
                animationEasing="ease-out"
              >
                {/* Value label on top of each bar */}
                <LabelList
                  dataKey={metric}
                  content={(props) => (
                    <BarTopLabel
                      {...(props as Parameters<typeof BarTopLabel>[0])}
                      metric={metric}
                    />
                  )}
                />
                {data.map((entry, i) => (
                  <Cell
                    key={`${uid}-cell-${i}`}
                    fill={
                      entry.isPredicted
                        ? `url(#${uid}-predicted)`
                        : `url(#${uid}-actual)`
                    }
                    stroke={entry.isPredicted ? predictedColor : "transparent"}
                    strokeWidth={entry.isPredicted ? 1.5 : 0}
                    strokeDasharray={entry.isPredicted ? "4 3" : undefined}
                  />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>

          <p className="mt-2 text-xs text-muted-foreground">
            Sem 1–6 show actual SGPA. Sem 7/8 show AI predicted SGPA. Hover a bar to view subject marks.
          </p>
        </>
      )}
    </ChartCard>
  )
}
