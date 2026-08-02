"use client"

import * as React from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer } from "@/components/shared/charts/chart-container"

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

export function SubjectBarChart({
  data,
  xKey,
  dataKey,
  color,
  height = 260,
}: {
  data: Array<Record<string, string | number>>
  xKey: string
  dataKey: string
  color: string
  height?: number
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

  const maxChars = width >= 900 ? 20 : width >= 560 ? 14 : 10

  function formatTick(value: string | number): string {
    const text = String(value)
    return text.length > maxChars ? `${text.slice(0, maxChars)}…` : text
  }

  return (
    <div ref={frameRef} className="w-full">
      <ChartContainer height={height}>
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }} barCategoryGap="28%">
          <defs>
            <linearGradient id={`${uid}-bar`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.9} />
              <stop offset="100%" stopColor={color} stopOpacity={0.55} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            stroke="var(--muted-foreground)"
            interval={0}
            angle={-35}
            textAnchor="end"
            height={88}
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
            content={<ChartTooltip />}
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            wrapperStyle={{ outline: "none" }}
          />
          <Bar
            dataKey={dataKey}
            fill={`url(#${uid}-bar)`}
            radius={[6, 6, 2, 2]}
            maxBarSize={48}
            isAnimationActive
            animationDuration={600}
            animationEasing="ease-out"
          />
        </BarChart>
      </ChartContainer>
    </div>
  )
}
