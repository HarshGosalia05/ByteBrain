"use client"

import * as React from "react"
import { Cell, Pie, PieChart, Tooltip } from "recharts"

import { ChartContainer } from "@/components/shared/charts/chart-container"

type DonutTooltipProps = {
  active?: boolean
  payload?: Array<{
    name?: string
    value?: number | string
    payload?: { name?: string; value?: number; percentage?: number; color?: string }
  }>
}

function DonutTooltip({ active, payload }: DonutTooltipProps) {
  if (!active || !payload?.length) return null
  const item = payload[0]?.payload
  if (!item) return null
  return (
    <div className="max-w-56 rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm">
      <p className="flex items-center justify-between gap-4 text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span
            className="size-2 shrink-0 rounded-full"
            style={{ backgroundColor: item.color }}
            aria-hidden="true"
          />
          {item.name}
        </span>
        <span className="font-medium tabular-nums text-foreground">{item.value}</span>
      </p>
    </div>
  )
}

export type DonutSlice = {
  name: string
  value: number
  color: string
}

export function DonutChart({
  data,
  height = 220,
  centerLabel,
  centerValue,
  centerHint,
}: {
  data: DonutSlice[]
  height?: number
  centerLabel?: string
  centerValue?: string
  centerHint?: string
}) {
  const uid = React.useId()
  const total = data.reduce((sum, slice) => sum + slice.value, 0)
  const withPercent = data.map((slice) => ({
    ...slice,
    percentage: total > 0 ? Math.round((slice.value / total) * 100) : 0,
  }))
  const active = withPercent.filter((slice) => slice.value > 0)

  return (
    <div className="flex w-full flex-col items-center gap-4">
      <div className="relative w-full max-w-56">
        <ChartContainer height={height}>
          <PieChart>
            <Tooltip content={<DonutTooltip />} wrapperStyle={{ outline: "none" }} />
            <Pie
              data={active}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="88%"
              paddingAngle={active.length > 1 ? 2 : 0}
              strokeWidth={0}
              isAnimationActive
              animationDuration={600}
              animationEasing="ease-out"
            >
              {active.map((slice) => (
                <Cell key={`${uid}-${slice.name}`} fill={slice.color} />
              ))}
            </Pie>
          </PieChart>
        </ChartContainer>
        {centerValue !== undefined && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-2xl font-semibold tracking-tight tabular-nums">
              {centerValue}
            </span>
            {centerLabel && (
              <span className="text-xs font-medium text-muted-foreground">{centerLabel}</span>
            )}
            {centerHint && <span className="text-[0.6875rem] text-muted-foreground">{centerHint}</span>}
          </div>
        )}
      </div>
      <div className="grid w-full grid-cols-2 gap-x-4 gap-y-2">
        {withPercent.map((slice) => (
          <div key={slice.name} className="flex items-center justify-between gap-2 text-xs">
            <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: slice.color }}
                aria-hidden="true"
              />
              <span className="truncate">{slice.name}</span>
            </span>
            <span className="shrink-0 font-medium tabular-nums text-foreground">
              {slice.value}
              <span className="ml-1 text-muted-foreground">({slice.percentage}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
