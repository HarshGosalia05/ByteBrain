"use client"

import * as React from "react"
import { ResponsiveContainer } from "recharts"

export function ChartContainer({
  height,
  children,
  className = "w-full",
}: {
  height: number
  children: React.ReactElement
  className?: string
}) {
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])

  return (
    <div style={{ height }} className={`min-w-0 ${className}`}>
      {mounted ? (
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      ) : null}
    </div>
  )
}
