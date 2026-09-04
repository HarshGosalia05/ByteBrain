"use client"

import * as React from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer } from "@/components/shared/charts/chart-container"

type SemesterChartData = {
  semester: string
  sgpa: number | null
  attendance: number | null
  percentage: number | null
}

type ChartTooltipProps = {
  active?: boolean
  label?: string | number
  payload?: Array<{ name?: string; value?: number | string | null; color?: string }>
}

function formatValue(item: { name?: string; value?: number | string | null }) {
  if (item.value === null || item.value === undefined) {
    return "Not entered"
  }
  if (item.name === "SGPA") {
    return Number(item.value).toFixed(2)
  }
  if (item.name === "Semester %") {
    return `${Number(item.value).toFixed(2)}%`
  }
  return `${Number(item.value).toFixed(1)}%`
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="max-w-56 rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm">
      <p className="font-medium text-foreground">{label}</p>
      <div className="mt-1.5 flex flex-col gap-1">
        {payload.map((item) => (
          <p
            key={item.name}
            className="flex items-center justify-between gap-4 text-muted-foreground"
          >
            <span className="flex items-center gap-1.5">
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              {item.name}
            </span>
            <span className="font-medium tabular-nums text-foreground">{formatValue(item)}</span>
          </p>
        ))}
      </div>
    </div>
  )
}

const LEGEND_ITEMS = [
  { key: "sgpa", label: "SGPA", color: "var(--chart-1)" },
  { key: "attendance", label: "Attendance %", color: "var(--chart-2)" },
  { key: "percentage", label: "Semester %", color: "var(--chart-3)" },
]

export function SemesterChart({
  data,
  height = 240,
}: {
  data: SemesterChartData[]
  height?: number
}) {
  const uid = React.useId()

  return (
    <div className="flex w-full flex-col">
      <div className="mb-3 flex flex-wrap items-center justify-end gap-x-4 gap-y-1">
        {LEGEND_ITEMS.map((item) => (
          <span
            key={item.key}
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            {item.label}
          </span>
        ))}
      </div>
      <ChartContainer height={height}>
        <AreaChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`${uid}-sgpa`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id={`${uid}-attendance`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--chart-2)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="var(--chart-2)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id={`${uid}-percentage`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--chart-3)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="var(--chart-3)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="semester"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              stroke="var(--muted-foreground)"
              tickMargin={10}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              stroke="var(--muted-foreground)"
              width={44}
              tickMargin={6}
              domain={[0, 10]}
              tickFormatter={(value: number) => value.toFixed(1)}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              stroke="var(--muted-foreground)"
              width={44}
              tickMargin={6}
              domain={[0, 100]}
              tickFormatter={(value: number) => `${value}%`}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
              wrapperStyle={{ outline: "none" }}
            />
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="sgpa"
              name="SGPA"
              stroke="var(--chart-1)"
              strokeWidth={2}
              strokeLinecap="round"
              fill={`url(#${uid}-sgpa)`}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }}
              isAnimationActive
              animationDuration={600}
              animationEasing="ease-out"
            />
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="attendance"
              name="Attendance %"
              stroke="var(--chart-2)"
              strokeWidth={2}
              strokeLinecap="round"
              fill={`url(#${uid}-attendance)`}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }}
              isAnimationActive
              animationDuration={600}
              animationEasing="ease-out"
            />
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="percentage"
              name="Semester %"
              stroke="var(--chart-3)"
              strokeWidth={2}
              strokeLinecap="round"
              fill={`url(#${uid}-percentage)`}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }}
              isAnimationActive
              animationDuration={600}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ChartContainer>
    </div>
  )
}