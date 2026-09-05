"use client"

import * as React from "react"
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts"

import { cn } from "@/lib/utils"
import { ChartContainer } from "@/components/shared/charts/chart-container"
import { ChartCard } from "@/components/shared/data/chart-card"

type Metric = "sgpa" | "percentage"

type ChartPoint = {
  label: string
  sgpa: number | null
  percentage: number | null
  isPredicted: boolean
  semesterNo: number | null
}

type TooltipPayloadItem = {
  name?: string
  value?: number | string
  color?: string
  payload?: ChartPoint
}

function MetricToggle({ metric, onChange }: { metric: Metric; onChange: (m: Metric) => void }) {
  return (
    <div className="flex items-center gap-1 rounded-md border border-input bg-background p-0.5">
      <button
        type="button"
        className={cn(
          "h-8 rounded px-2.5 text-sm font-medium transition-colors",
          metric === "sgpa" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
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
          metric === "percentage" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
        onClick={() => onChange("percentage")}
        aria-pressed={metric === "percentage"}
      >
        %
      </button>
    </div>
  )
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayloadItem[]; label?: string | number }) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload as ChartPoint | undefined
  return (
    <div className="max-w-56 rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm">
      <p className="font-medium text-foreground">{label}</p>
      {point?.isPredicted && <p className="mt-0.5 text-muted-foreground">AI predicted</p>}
      <div className="mt-1.5 flex flex-col gap-1">
        {payload.map((item, i) => (
          <p key={`${item.name}-${i}`} className="flex items-center justify-between gap-4 text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              {item.name}
            </span>
            <span className="font-medium tabular-nums text-foreground">{item.value}</span>
          </p>
        ))}
      </div>
    </div>
  )
}

export function SemesterTrendChart({
  history,
  predictedNextSemester,
  currentSemester,
}: {
  history: Array<{ semester_no: number; semester_sgpa: number | null; semester_percentage: number | null }>
  predictedNextSemester: { sgpa: number | null; percentage: number | null; semester_no: number | null } | null
  currentSemester: { semester_no: number | null; predictedMarks: number[] } | null
}) {
  const [metric, setMetric] = React.useState<Metric>("sgpa")
  const uid = React.useId()

  const currentSemNo = currentSemester?.semester_no ?? null

  const actualPoints = history
    .filter(
      (p) =>
        // Only completed semesters (published result) are charted. Placeholder
        // rows for an in-progress semester carry sgpa=0 / percentage=0 and
        // would draw a misleading zero bar.
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

  const currentSemPoint: ChartPoint | null = (() => {
    if (!currentSemester || currentSemester.predictedMarks.length === 0) return null
    const avgMarks =
      currentSemester.predictedMarks.reduce((acc, m) => acc + m, 0) /
      currentSemester.predictedMarks.length
    const pct = avgMarks / 70 * 100
    const sgpa = avgMarks / 70 * 10
    return {
      label: currentSemester.semester_no
        ? `Sem ${currentSemester.semester_no} (AI)`
        : "Current Sem (AI)",
      sgpa,
      percentage: pct,
      isPredicted: true,
      semesterNo: currentSemester.semester_no,
    }
  })()

  const predictedPoint: ChartPoint | null =
    predictedNextSemester &&
    (predictedNextSemester.sgpa !== null || predictedNextSemester.percentage !== null) &&
    (currentSemester === null || predictedNextSemester.semester_no !== currentSemester.semester_no)
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
      subtitle="SGPA / percentage across completed semesters, with the next semester projected by the AI model."
      status={hasAny ? "ready" : "empty"}
      emptyTitle="No trend data"
      emptyDescription="There is no semester performance data available to chart yet."
    >
      {hasAny && (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: actualColor }} />
                Completed semester
              </span>
              {currentSemPoint && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: predictedColor }} />
                  AI predicted (current semester)
                </span>
              )}
              {predictedPoint && !currentSemPoint && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: predictedColor }} />
                  AI predicted (next semester)
                </span>
              )}
              {predictedPoint && currentSemPoint && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: predictedColor }} />
                  AI predicted
                </span>
              )}
            </div>
            <MetricToggle metric={metric} onChange={setMetric} />
          </div>

          <ChartContainer height={260}>
            <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }} barCategoryGap="24%">
              <defs>
                <linearGradient id={`${uid}-actual`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={actualColor} stopOpacity={0.9} />
                  <stop offset="100%" stopColor={actualColor} stopOpacity={0.5} />
                </linearGradient>
                <linearGradient id={`${uid}-predicted`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={predictedColor} stopOpacity={0.9} />
                  <stop offset="100%" stopColor={predictedColor} stopOpacity={0.55} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
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
                tickFormatter={(v: number) => (metric === "sgpa" ? v.toFixed(1) : `${v}%`)}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} wrapperStyle={{ outline: "none" }} />
              <ReferenceLine
                y={metric === "sgpa" ? 7 : 70}
                stroke="var(--muted-foreground)"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{ value: "Target", fontSize: 10, fill: "var(--muted-foreground)", position: "insideTopLeft" }}
              />
              <Bar dataKey={metric} name={metric === "sgpa" ? "SGPA" : "Percentage"} radius={[6, 6, 2, 2]} maxBarSize={52} isAnimationActive animationDuration={600} animationEasing="ease-out">
                {data.map((entry, i) => (
                  <Cell
                    key={`${uid}-cell-${i}`}
                    fill={entry.isPredicted ? `url(#${uid}-predicted)` : `url(#${uid}-actual)`}
                    stroke={entry.isPredicted ? predictedColor : "transparent"}
                    strokeWidth={entry.isPredicted ? 1.5 : 0}
                    strokeDasharray={entry.isPredicted ? "4 3" : undefined}
                  />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>

          <p className="mt-2 text-xs text-muted-foreground">
            Highlighted bars are AI model estimates (average predicted subject marks for the current
            semester, and next-semester forecast), not actual results.
          </p>
        </>
      )}
    </ChartCard>
  )
}
