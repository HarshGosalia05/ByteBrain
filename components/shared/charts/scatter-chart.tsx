"use client"

import {
  CartesianGrid,
  ReferenceLine,
  Scatter,
  ScatterChart as RechartsScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer } from "@/components/shared/charts/chart-container"

export type ScatterPoint = {
  x: number
  y: number
}

export type ScatterReferenceLine = {
  x?: number
  y?: number
  label?: string
  stroke?: string
}

type ScatterTooltipProps = {
  active?: boolean
  payload?: Array<{ payload?: ScatterPoint }>
}

function ScatterTooltip({ active, payload }: ScatterTooltipProps) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm">
      <p className="font-medium text-foreground">Attendance vs performance</p>
      <p className="mt-1 text-muted-foreground">
        Attendance{" "}
        <span className="font-medium tabular-nums text-foreground">{point.x}%</span> · Performance{" "}
        <span className="font-medium tabular-nums text-foreground">{point.y}%</span>
      </p>
    </div>
  )
}

export function ScatterChart({
  data,
  height = 260,
  referenceLines = [],
}: {
  data: ScatterPoint[]
  height?: number
  referenceLines?: ScatterReferenceLine[]
}) {
  return (
    <ChartContainer height={height}>
      <RechartsScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="x"
          type="number"
          domain={[0, 100]}
          tick={{ fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          stroke="var(--muted-foreground)"
          tickMargin={6}
          label={{
            value: "Attendance %",
            position: "insideBottom",
            offset: -6,
            fontSize: 11,
            fill: "var(--muted-foreground)",
          }}
        />
        <YAxis
          dataKey="y"
          type="number"
          domain={[0, 100]}
          tick={{ fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          stroke="var(--muted-foreground)"
          width={44}
          tickMargin={6}
          label={{
            value: "Performance %",
            angle: -90,
            position: "insideLeft",
            offset: 4,
            fontSize: 11,
            fill: "var(--muted-foreground)",
          }}
        />
        <Tooltip
          content={<ScatterTooltip />}
          cursor={{ strokeDasharray: "3 3" }}
          wrapperStyle={{ outline: "none" }}
        />
        {referenceLines.map((rl, i) => (
          <ReferenceLine
            key={i}
            x={rl.x}
            y={rl.y}
            stroke={rl.stroke ?? "var(--destructive)"}
            strokeWidth={1.5}
            strokeDasharray="5 5"
            label={
              rl.label
                ? {
                    value: rl.label,
                    fontSize: 11,
                    fill: "var(--muted-foreground)",
                    position: "insideTopRight",
                  }
                : undefined
            }
          />
        ))}
        <Scatter
          data={data}
          fill="var(--chart-4)"
          isAnimationActive
          animationDuration={600}
          animationEasing="ease-out"
        />
      </RechartsScatterChart>
    </ChartContainer>
  )
}
