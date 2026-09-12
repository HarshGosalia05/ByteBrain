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

export function DashboardPreview() {
  const [hoveredSubject, setHoveredSubject] = React.useState<string | null>(null)

  return (
    <div className="relative w-full rounded-2xl border border-border/80 bg-card/90 p-5 sm:p-6 shadow-2xl ring-1 ring-foreground/5 backdrop-blur-xl transition-all duration-300">
      {/* Subtle top ambient highlight */}
      <div
        className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 w-3/4 h-20 bg-primary/10 blur-2xl rounded-full"
        aria-hidden="true"
      />

      {/* 1. Header Bar: Window Controls + Title + Live Status */}
      <div className="mb-4 sm:mb-5 flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-destructive/70" />
            <span className="size-2.5 rounded-full bg-chart-3/70" />
            <span className="size-2.5 rounded-full bg-chart-2/70" />
          </div>
          <span className="ml-2 text-xs font-semibold tracking-wide text-foreground">
            CampusX Intelligence Console
          </span>
        </div>

        {/* Live status indicator */}
        <div
          className="flex items-center gap-2 rounded-full border border-chart-2/30 bg-chart-2/10 px-2.5 py-1"
          aria-label="Status: LIVE - System Active"
        >
          <span className="relative flex size-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-2 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-chart-2" />
          </span>
          <div className="flex items-center gap-1.5 text-[0.7rem] leading-none">
            <span className="font-bold tracking-wider text-chart-2 uppercase text-[0.68rem]">
              LIVE
            </span>
            <span className="text-muted-foreground/40 font-light">|</span>
            <span className="font-medium text-foreground">
              System Active
            </span>
          </div>
        </div>
      </div>

      {/* 2. Student Snapshot Header (Clean, spacious, informative) */}
      <div className="mb-4 sm:mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 rounded-xl border border-border/60 bg-muted/20 p-3.5 sm:p-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 border border-primary/30 text-primary font-bold text-sm shadow-xs">
            AP
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm sm:text-base font-bold text-foreground">
                Aarav Patel
              </h4>
              <span className="inline-flex items-center gap-1 rounded-full bg-chart-2/10 border border-chart-2/25 px-2 py-0.5 text-[0.65rem] font-medium text-chart-2">
                <CheckCircle2 className="size-2.5" />
                Good Standing
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              B.Tech Computer Science · Semester 6
            </p>
          </div>
        </div>

        {/* Key Metrics Pills */}
        <div className="flex items-center gap-2 sm:gap-3 self-stretch sm:self-auto justify-between sm:justify-end">
          <div className="rounded-lg border border-border/50 bg-background/60 px-3 py-1.5 text-left sm:text-right">
            <p className="text-[0.65rem] font-medium uppercase tracking-wider text-muted-foreground">
              Academic Standing
            </p>
            <div className="flex items-baseline gap-1.5 sm:justify-end">
              <span className="text-sm sm:text-base font-bold text-foreground">8.42</span>
              <span className="text-[0.65rem] font-semibold text-chart-2 flex items-center">
                <TrendingUp className="size-2.5 mr-0.5" /> Top 5%
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-border/50 bg-background/60 px-3 py-1.5 text-left sm:text-right">
            <p className="text-[0.65rem] font-medium uppercase tracking-wider text-muted-foreground">
              Attendance
            </p>
            <div className="flex items-baseline gap-1.5 sm:justify-end">
              <span className="text-sm sm:text-base font-bold text-chart-2">88.4%</span>
              <span className="text-[0.65rem] text-muted-foreground">On Track</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Core Intelligence Cards (2 Balanced Columns) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 sm:gap-4">
        {/* Left Card: AI Grade Predictions */}
        <div className="rounded-xl border border-border/60 bg-muted/20 p-4 transition-all duration-200 hover:border-primary/40">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
                <GraduationCap className="size-4" />
              </div>
              <div>
                <h5 className="text-xs font-bold text-foreground">
                  Performance Predictions
                </h5>
                <p className="text-[0.68rem] text-muted-foreground">
                  AI-forecasted end-sem outcomes
                </p>
              </div>
            </div>
            <span className="rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-[0.65rem] font-medium text-primary">
              High Confidence
            </span>
          </div>

          {/* Subjects List */}
          <div className="space-y-2">
            <div
              className={cn(
                "rounded-lg p-2.5 transition-all duration-150 border cursor-pointer",
                hoveredSubject === "cs601"
                  ? "bg-primary/10 border-primary/30"
                  : "bg-background/40 hover:bg-background/70 border-border/30"
              )}
              onMouseEnter={() => setHoveredSubject("cs601")}
              onMouseLeave={() => setHoveredSubject(null)}
            >
              <div className="flex justify-between items-center text-xs mb-1.5">
                <span className="font-medium text-foreground">Data Mining (CS601)</span>
                <span className="font-bold text-foreground">
                  61.5 / 70 <span className="text-chart-2 ml-1">Grade AA</span>
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-border/50 overflow-hidden">
                <div
                  className="h-full rounded-full bg-chart-2 transition-all duration-300"
                  style={{ width: "88%" }}
                />
              </div>
            </div>

            <div
              className={cn(
                "rounded-lg p-2.5 transition-all duration-150 border cursor-pointer",
                hoveredSubject === "cs602"
                  ? "bg-primary/10 border-primary/30"
                  : "bg-background/40 hover:bg-background/70 border-border/30"
              )}
              onMouseEnter={() => setHoveredSubject("cs602")}
              onMouseLeave={() => setHoveredSubject(null)}
            >
              <div className="flex justify-between items-center text-xs mb-1.5">
                <span className="font-medium text-foreground">Machine Learning (CS602)</span>
                <span className="font-bold text-foreground">
                  58.0 / 70 <span className="text-primary ml-1">Grade AB</span>
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-border/50 overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-300"
                  style={{ width: "83%" }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Card: Risk Status & Career Alignment */}
        <div className="rounded-xl border border-border/60 bg-muted/20 p-4 flex flex-col justify-between transition-all duration-200 hover:border-primary/40">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-chart-2/10 text-chart-2">
                  <ShieldCheck className="size-4" />
                </div>
                <div>
                  <h5 className="text-xs font-bold text-foreground">
                    Academic Risk & Career
                  </h5>
                  <p className="text-[0.68rem] text-muted-foreground">
                    Risk screening and pathway match
                  </p>
                </div>
              </div>
              <span className="rounded-md border border-chart-2/30 bg-chart-2/10 px-2 py-0.5 text-[0.65rem] font-medium text-chart-2">
                Low Risk
              </span>
            </div>

            {/* Career Readiness Progress */}
            <div className="rounded-lg bg-background/40 border border-border/30 p-2.5 mb-2.5">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <div className="flex items-center gap-1.5">
                  <Briefcase className="size-3.5 text-primary" />
                  <span className="font-medium text-foreground">Target: AI/ML Engineer</span>
                </div>
                <span className="font-bold text-primary">82% Match</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-border/50 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-primary to-chart-2 transition-all duration-300"
                  style={{ width: "82%" }}
                />
              </div>
            </div>
          </div>

          {/* Quick Guidance Recommendation */}
          <div className="flex items-center gap-2 rounded-lg bg-primary/5 border border-primary/20 px-3 py-2 text-[0.72rem] text-muted-foreground mt-1">
            <Sparkles className="size-3.5 text-primary shrink-0" />
            <span className="text-foreground/90">
              <strong className="font-semibold text-primary">AI Guidance:</strong> Strong core fundamentals in Python & Algorithms.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
