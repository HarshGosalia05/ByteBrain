"use client"

import * as React from "react"
import {
  TrendingUp,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  GraduationCap,
  Briefcase,
} from "lucide-react"

import { cn } from "@/lib/utils"

function AnimateIn({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  const [visible, setVisible] = React.useState(false)
  React.useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(t)
  }, [delay])
  return (
    <div
      className={cn(
        "transition-all duration-700 ease-out",
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2",
        className
      )}
    >
      {children}
    </div>
  )
}

function AnimatedBar({
  width,
  color,
  delay = 0,
}: {
  width: string
  color: string
  delay?: number
}) {
  const [w, setW] = React.useState("0%")
  React.useEffect(() => {
    const t = setTimeout(() => setW(width), delay)
    return () => clearTimeout(t)
  }, [width, delay])
  return (
    <div className="h-full rounded-full bg-white/[0.06] overflow-hidden">
      <div
        className={cn("h-full rounded-full transition-all duration-1000 ease-out", color)}
        style={{ width: w }}
      />
    </div>
  )
}

export function DashboardPreview() {
  const [hoveredSubject, setHoveredSubject] = React.useState<string | null>(null)

  return (
    <div className="relative w-full rounded-2xl border border-white/[0.08] bg-[#0c0f1a]/95 p-4 sm:p-5 shadow-[0_0_60px_-12px_rgba(56,189,248,0.15)] ring-1 ring-white/[0.05] backdrop-blur-2xl transition-all duration-300 hover:shadow-[0_0_80px_-12px_rgba(56,189,248,0.2)]">
      {/* Top ambient glow */}
      <div
        className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 w-3/4 h-16 bg-sky-500/10 blur-3xl rounded-full"
        aria-hidden="true"
      />

      {/* 1. Header Bar */}
      <div className="mb-4 sm:mb-5 flex items-center justify-between gap-2 border-b border-white/[0.06] pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-red-500/70" />
            <span className="size-2.5 rounded-full bg-yellow-500/70" />
            <span className="size-2.5 rounded-full bg-green-500/70" />
          </div>
          <span className="ml-2 text-xs font-semibold tracking-wide text-white/90">
            CampusX Intelligence Console
          </span>
        </div>

        {/* Live status indicator */}
        <div
          className="flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1"
          aria-label="Status: LIVE - System Active"
        >
          <span className="relative flex size-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
          </span>
          <div className="flex items-center gap-1.5 text-[0.7rem] leading-none">
            <span className="font-bold tracking-wider text-emerald-400 uppercase text-[0.68rem]">
              LIVE
            </span>
            <span className="text-white/20 font-light">|</span>
            <span className="font-medium text-white/70">System Active</span>
          </div>
        </div>
      </div>

      {/* 2. Student Snapshot */}
      <AnimateIn delay={100}>
        <div className="mb-4 sm:mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 sm:p-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/15 border border-sky-500/25 text-sky-400 font-bold text-sm shadow-sm">
              AP
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm sm:text-base font-bold text-white/95">Aarav Patel</h4>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 px-2 py-0.5 text-[0.65rem] font-medium text-emerald-400">
                  <CheckCircle2 className="size-2.5" />
                  Good Standing
                </span>
              </div>
              <p className="text-xs text-white/40">B.Tech Computer Science · Semester 6</p>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="flex items-center gap-2 sm:gap-3 self-stretch sm:self-auto justify-between sm:justify-end">
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.04] px-3 py-2 text-left sm:text-right">
              <p className="text-[0.6rem] font-semibold uppercase tracking-widest text-white/35">
                Academic Standing
              </p>
              <div className="flex items-baseline gap-1.5 sm:justify-end mt-0.5">
                <span className="text-sm sm:text-lg font-bold text-white/95">8.42</span>
                <span className="text-[0.65rem] font-semibold text-emerald-400 flex items-center">
                  <TrendingUp className="size-2.5 mr-0.5" /> Top 5%
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-white/[0.04] px-3 py-2 text-left sm:text-right">
              <p className="text-[0.6rem] font-semibold uppercase tracking-widest text-white/35">
                Attendance
              </p>
              <div className="flex items-baseline gap-1.5 sm:justify-end mt-0.5">
                <span className="text-sm sm:text-lg font-bold text-emerald-400">88.4%</span>
                <span className="text-[0.65rem] text-white/35">On Track</span>
              </div>
            </div>
          </div>
        </div>
      </AnimateIn>

      {/* 3. Intelligence Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-3.5">
        {/* Left Card: Performance Predictions */}
        <AnimateIn delay={250}>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 sm:p-4 transition-all duration-200 hover:border-sky-500/20 hover:bg-white/[0.05]">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400">
                  <GraduationCap className="size-4" />
                </div>
                <div>
                  <h5 className="text-xs font-bold text-white/90">Performance Predictions</h5>
                  <p className="text-[0.68rem] text-white/35">AI-forecasted end-sem outcomes</p>
                </div>
              </div>
              <span className="rounded-md border border-sky-400/25 bg-sky-500/10 px-2 py-0.5 text-[0.65rem] font-medium text-sky-400">
                High Confidence
              </span>
            </div>

            {/* Subjects */}
            <div className="space-y-2">
              <div
                className={cn(
                  "rounded-lg p-2.5 transition-all duration-150 border cursor-pointer",
                  hoveredSubject === "cs601"
                    ? "bg-sky-500/10 border-sky-500/25"
                    : "bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.04]"
                )}
                onMouseEnter={() => setHoveredSubject("cs601")}
                onMouseLeave={() => setHoveredSubject(null)}
              >
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <span className="font-medium text-white/80">Data Mining (CS601)</span>
                  <span className="font-bold text-white/90">
                    61.5 / 70{" "}
                    <span className="text-emerald-400 ml-1 text-[0.7rem]">Grade AA</span>
                  </span>
                </div>
                <div className="h-1.5 w-full">
                  <AnimatedBar
                    width="88%"
                    color="bg-emerald-400"
                    delay={400}
                  />
                </div>
              </div>

              <div
                className={cn(
                  "rounded-lg p-2.5 transition-all duration-150 border cursor-pointer",
                  hoveredSubject === "cs602"
                    ? "bg-sky-500/10 border-sky-500/25"
                    : "bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.04]"
                )}
                onMouseEnter={() => setHoveredSubject("cs602")}
                onMouseLeave={() => setHoveredSubject(null)}
              >
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <span className="font-medium text-white/80">Machine Learning (CS602)</span>
                  <span className="font-bold text-white/90">
                    58.0 / 70{" "}
                    <span className="text-sky-400 ml-1 text-[0.7rem]">Grade AB</span>
                  </span>
                </div>
                <div className="h-1.5 w-full">
                  <AnimatedBar
                    width="83%"
                    color="bg-sky-400"
                    delay={500}
                  />
                </div>
              </div>
            </div>
          </div>
        </AnimateIn>

        {/* Right Card: Academic Risk & Career */}
        <AnimateIn delay={350}>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 sm:p-4 flex flex-col justify-between transition-all duration-200 hover:border-sky-500/20 hover:bg-white/[0.05]">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                    <ShieldCheck className="size-4" />
                  </div>
                  <div>
                    <h5 className="text-xs font-bold text-white/90">
                      Academic Risk &amp; Career
                    </h5>
                    <p className="text-[0.68rem] text-white/35">
                      Risk screening and pathway match
                    </p>
                  </div>
                </div>
                <span className="rounded-md border border-emerald-400/25 bg-emerald-500/10 px-2 py-0.5 text-[0.65rem] font-medium text-emerald-400">
                  Low Risk
                </span>
              </div>

              {/* Career Match */}
              <div className="rounded-lg bg-white/[0.03] border border-white/[0.05] p-2.5 mb-2.5">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <Briefcase className="size-3.5 text-sky-400" />
                    <span className="font-medium text-white/80">Target: AI/ML Engineer</span>
                  </div>
                  <span className="font-bold text-sky-400">82% Match</span>
                </div>
                <div className="h-1.5 w-full">
                  <AnimatedBar
                    width="82%"
                    color="bg-gradient-to-r from-sky-400 to-emerald-400"
                    delay={500}
                  />
                </div>
              </div>
            </div>

            {/* AI Guidance */}
            <div className="flex items-start gap-2 rounded-lg bg-sky-500/[0.06] border border-sky-500/15 px-3 py-2.5 text-[0.72rem] mt-1">
              <Sparkles className="size-3.5 text-sky-400 shrink-0 mt-0.5" />
              <span className="text-white/60 leading-relaxed">
                <strong className="font-semibold text-sky-400">AI Guidance:</strong>{" "}
                Strong core fundamentals in Python &amp; Algorithms.
              </span>
            </div>
          </div>
        </AnimateIn>
      </div>
    </div>
  )
}
