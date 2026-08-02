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

export type ChartSeries = {
  key: string
  label: string
  color: string
}

type ChartTooltipProps = {
  active?: boolean
  label?: string | number
  payload?: Array<{ name?: string; value?: number | string; color?: string }>
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
            <span className="font-medium tabular-nums text-foreground">{item.value}</span>
          </p>
        ))}
      </div>
    </div>
  )
}

export function TrendChart({
  data,
  xKey,
  series,
  height = 240,
  yDomain,
  yTickSuffix,
}: {
  data: Array<Record<string, string | number>>
  xKey: string
  series: ChartSeries[]
  height?: number
  yDomain?: [number | "auto", number | "auto"]
  yTickSuffix?: string
}) {
  const uid = React.useId()

  return (
    <div className="flex w-full flex-col">
      <div className="mb-3 flex flex-wrap items-center justify-end gap-x-4 gap-y-1">
        {series.map((s) => (
          <span
            key={s.key}
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: s.color }}
              aria-hidden="true"
            />
            {s.label}
          </span>
        ))}
      </div>
      <ChartContainer height={height}>
        <AreaChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <defs>
              {series.map((s) => (
                <linearGradient key={s.key} id={`${uid}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={s.color} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={s.color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey={xKey}
              tick={{ fontSize: 12 }}
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
              tickFormatter={yTickSuffix ? (value: number) => `${value}${yTickSuffix}` : undefined}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
              wrapperStyle={{ outline: "none" }}
            />
            {series.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                strokeLinecap="round"
                fill={`url(#${uid}-${s.key})`}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }}
                isAnimationActive
                animationDuration={600}
                animationEasing="ease-out"
              />
            ))}
          </AreaChart>
        </ChartContainer>
    </div>
  )
}
