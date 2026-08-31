"use client"

import * as React from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer } from "@/components/shared/charts/chart-container"

type ChartTooltipProps = {
  active?: boolean
  label?: string | number
  payload?: ReadonlyArray<{ name?: string | number; value?: number | string | number; color?: string }>
  subject_name?: string
}

function ChartTooltip({ active, payload, label, subject_name }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="max-w-56 rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm">
      <p className="font-medium text-foreground">{label}</p>
      {subject_name && (
        <p className="mt-0.5 text-muted-foreground">{subject_name}</p>
      )}
      <div className="mt-1.5 flex flex-col gap-1">
        {payload.map((item, i) => (
          <p
            key={`${item.name}-${i}`}
            className="flex items-center justify-between gap-4 text-muted-foreground"
          >
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

export type ChartBar = {
  dataKey: string
  name: string
  color: string
}

export type ChartReferenceLine = {
  x?: string | number
  y?: string | number
  label?: string
  position?: "start" | "middle" | "end"
  stroke?: string
}

export function SubjectBarChart({
  data,
  xKey,
  dataKey,
  color,
  height = 260,
  onBarClick,
  bars,
  referenceLines,
  compact = false,
}: {
  data: Array<Record<string, string | number | null>>
  xKey: string
  dataKey?: string
  color?: string
  height?: number
  onBarClick?: (entry: Record<string, string | number>) => void
  bars?: ChartBar[]
  referenceLines?: ChartReferenceLine[]
  compact?: boolean
}) {
  const uid = React.useId()
  const frameRef = React.useRef<HTMLDivElement>(null)
  const [width, setWidth] = React.useState(0)

  React.useEffect(() => {
    const el = frameRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      setWidth(entries[0]?.contentRect.width ?? 0)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const dataCount = data.length
  const series: ChartBar[] =
    bars ?? (dataKey && color ? [{ dataKey, name: "Count", color }] : [])
  const perCategoryColors =
    !!bars && bars.length > 1 && bars.every((b) => b.dataKey === bars[0].dataKey)

  // Adaptive label settings based on data count and container width
  const isDense = dataCount > 20
  const isVeryDense = dataCount > 35

  const maxChars = isVeryDense ? 8 : isDense ? 10 : width >= 900 ? 20 : width >= 560 ? 14 : 10
  const angle = isVeryDense ? -65 : isDense ? -50 : -35
  const labelHeight = isVeryDense ? 110 : isDense ? 96 : 88
  const bottomMargin = isVeryDense ? 20 : isDense ? 12 : 4
  const tickFontSize = isVeryDense ? 9 : isDense ? 10 : 11
  const barGap = isVeryDense ? "12%" : isDense ? "18%" : "28%"
  const tickInterval = isDense ? "preserveStartEnd" : 0
  const maxBar = compact ? 32 : isVeryDense ? 28 : isDense ? 36 : 48

  function formatTick(value: string | number): string {
    const text = String(value)
    return text.length > maxChars ? `${text.slice(0, maxChars)}…` : text
  }

  if (series.length === 0) {
    return null
  }

  return (
    <div ref={frameRef} className="w-full min-w-0">
      {bars && (
        <div className="mb-3 flex flex-wrap items-center justify-end gap-x-4 gap-y-1">
          {bars.map((b, i) => (
            <span
              key={`${b.dataKey}-${b.name}-${i}`}
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: b.color }} />
              {b.name}
            </span>
          ))}
        </div>
      )}
      <ChartContainer height={height}>
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: bottomMargin, left: 0 }} barCategoryGap={barGap}>
          <defs>
            <linearGradient id={`${uid}-bar`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={series[0].color} stopOpacity={0.9} />
              <stop offset="100%" stopColor={series[0].color} stopOpacity={0.55} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: tickFontSize }}
            tickLine={false}
            axisLine={false}
            stroke="var(--muted-foreground)"
            interval={tickInterval}
            angle={angle}
            textAnchor="end"
            height={labelHeight}
            tickMargin={10}
            tickFormatter={formatTick}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            stroke="var(--muted-foreground)"
            width={44}
            tickMargin={6}
          />
          <Tooltip
            content={({ active, payload, label }) => {
              const subjectName = payload?.[0]?.payload?.subject_name as string | undefined
              return (
                <ChartTooltip
                  active={active}
                  payload={payload as ChartTooltipProps["payload"]}
                  label={label}
                  subject_name={subjectName}
                />
              )
            }}
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            wrapperStyle={{ outline: "none" }}
          />
          {referenceLines?.map((rl, i) => (
            <ReferenceLine
              key={i}
              x={rl.x}
              y={rl.y}
              stroke={rl.stroke ?? "var(--destructive)"}
              strokeWidth={1.5}
              strokeDasharray="5 5"
              position={rl.position}
              label={
                rl.label
                  ? {
                      value: rl.label,
                      fontSize: 11,
                      fill: "var(--muted-foreground)",
                      position: rl.x !== undefined ? "insideTop" : "insideTopLeft",
                    }
                  : undefined
              }
            />
          ))}
          {series.map((s) => (
            <Bar
              key={`${s.dataKey}-${s.name}`}
              dataKey={s.dataKey}
              name={s.name}
              fill={bars ? s.color : `url(#${uid}-bar)`}
              radius={[6, 6, 2, 2]}
              maxBarSize={maxBar}
              isAnimationActive
              animationDuration={600}
              animationEasing="ease-out"
              {...(onBarClick
                ? {
                    onClick: (data: { payload?: Record<string, string | number> }) =>
                      onBarClick(data.payload ?? {}),
                    className: "cursor-pointer",
                  }
                : {})}
            >
              {perCategoryColors &&
                data.map((entry, i) => (
                  <Cell
                    key={`${uid}-cell-${i}`}
                    fill={bars?.[i]?.color ?? series[0].color}
                  />
                ))}
            </Bar>
          ))}
        </BarChart>
      </ChartContainer>
    </div>
  )
}
