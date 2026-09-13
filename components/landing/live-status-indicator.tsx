"use client"

import * as React from "react"
import { Activity, CheckCircle2, XCircle, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

type SystemHealth = {
  backend: "healthy" | "degraded" | "unavailable"
  database: "connected" | "unavailable"
  checkedAt: string
}

export function LiveStatusIndicator({
  health,
  className,
}: {
  health: SystemHealth
  className?: string
}) {
  const [open, setOpen] = React.useState(false)
  const panelRef = React.useRef<HTMLDivElement>(null)
  const buttonRef = React.useRef<HTMLButtonElement>(null)

  const isHealthy = health.backend === "healthy" && health.database === "connected"
  const isDegraded = health.backend === "degraded" || (health.backend === "healthy" && health.database !== "connected")

  React.useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", handleClickOutside)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open])

  function StatusDot({ ok }: { ok: boolean }) {
    return ok ? (
      <CheckCircle2 className="size-3.5 text-emerald-400" />
    ) : (
      <XCircle className="size-3.5 text-red-400" />
    )
  }

  return (
    <div className={cn("relative", className)}>
      <button
        ref={buttonRef}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-all",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          isHealthy
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
            : isDegraded
              ? "border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              : "border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20",
        )}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <span className="relative flex size-2">
          <span
            className={cn(
              "absolute inline-flex size-full animate-ping rounded-full opacity-75",
              isHealthy ? "bg-emerald-400" : isDegraded ? "bg-amber-400" : "bg-red-400",
            )}
          />
          <span
            className={cn(
              "relative inline-flex size-2 rounded-full",
              isHealthy ? "bg-emerald-400" : isDegraded ? "bg-amber-400" : "bg-red-400",
            )}
          />
        </span>
        <span className="font-semibold tracking-wide">LIVE</span>
        <span className="hidden sm:inline text-[0.65rem] opacity-70">| System Active</span>
      </button>

      {open && (
        <div
          ref={panelRef}
          role="menu"
          className={cn(
            "absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-xl border",
            "border-border/60 bg-card/95 shadow-xl shadow-black/20 backdrop-blur-xl",
            "ring-1 ring-foreground/5",
          )}
        >
          <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-primary" />
              <span className="text-sm font-semibold">System Status</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="rounded-md p-1 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <XCircle className="size-3.5" />
            </button>
          </div>

          <div className="space-y-0 divide-y divide-border/30">
            <StatusRow
              label="Backend API"
              status={health.backend === "healthy" ? "operational" : health.backend === "degraded" ? "degraded" : "unavailable"}
              ok={health.backend === "healthy"}
            />
            <StatusRow
              label="Database"
              status={health.database === "connected" ? "connected" : "unavailable"}
              ok={health.database === "connected"}
            />
            <StatusRow
              label="Frontend"
              status="active"
              ok={true}
            />
          </div>

          <div className="border-t border-border/30 px-4 py-2.5">
            <div className="flex items-center gap-1.5 text-[0.65rem] text-muted-foreground">
              <RefreshCw className="size-3" />
              <span>
                Last check:{" "}
                {new Date(health.checkedAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  function StatusRow({
    label,
    status,
    ok,
  }: {
    label: string
    status: string
    ok: boolean
  }) {
    return (
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <StatusDot ok={ok} />
          <span className="text-xs font-medium">{label}</span>
        </div>
        <span
          className={cn(
            "text-[0.65rem] font-medium capitalize",
            ok ? "text-emerald-400" : "text-red-400",
          )}
        >
          {status}
        </span>
      </div>
    )
  }
}
