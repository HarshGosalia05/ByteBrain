export type HorizontalBarItem = {
  id: string
  label: string
  value: number
  display: string
  hint?: string
}

export function HorizontalBars({
  items,
  color = "var(--chart-1)",
  maxValue = 100,
  labelWidthClass = "w-40",
}: {
  items: HorizontalBarItem[]
  color?: string
  maxValue?: number
  labelWidthClass?: string
}) {
  if (items.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => {
        const width = maxValue > 0 ? Math.max(2, (item.value / maxValue) * 100) : 2
        return (
          <div key={item.id} className="flex items-center gap-3">
            <span className={`${labelWidthClass} min-w-0 shrink-0 truncate text-xs text-muted-foreground`} title={item.label}>
              {item.label}
            </span>
            <div className="relative h-5 min-w-0 flex-1 overflow-hidden rounded-md bg-muted">
              <div
                className="h-full rounded-md"
                style={{ width: `${Math.min(width, 100)}%`, backgroundColor: color }}
              />
            </div>
            <span className="w-20 shrink-0 text-right text-xs font-medium tabular-nums text-foreground">
              {item.display}
            </span>
          </div>
        )
      })}
    </div>
  )
}
