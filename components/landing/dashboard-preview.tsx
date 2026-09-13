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

type TabKey = "all" | "m1v3" | "m3-risk" | "m4-career"

const TAB_OPTIONS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All Signals" },
  { key: "m1v3", label: "M1_v3" },
  { key: "m3-risk", label: "M3 Risk" },
  { key: "m4-career", label: "M4 Career" },
]

/* ── Tab Panels ──────────────────────────────────────────── */

function AllSignalsPanel({
  hoveredSubject,
  setHoveredSubject,
}: {
  hoveredSubject: string | null
  setHoveredSubject: (v: string | null) => void
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5 sm:p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <div className="p-1 rounded-md bg-sky-500/10 text-sky-400">
              <GraduationCap className="size-3" />
            </div>
            <h5 className="text-[0.68rem] font-bold text-white/90">Performance</h5>
          </div>
          <span className="rounded-md border border-sky-400/25 bg-sky-500/10 px-1.5 py-px text-[0.6rem] font-medium text-sky-400">
            High Confidence
          </span>
        </div>
        <div className="space-y-1.5">
          {[
            { id: "cs601", name: "Data Mining (CS601)", marks: "61.5/70", grade: "AA", pct: "88%", color: "bg-emerald-400" },
            { id: "cs602", name: "Machine Learning (CS602)", marks: "58.0/70", grade: "AB", pct: "83%", color: "bg-sky-400" },
          ].map((s) => (
            <div
              key={s.id}
              className={cn(
                "rounded-md p-2 transition-all duration-150 border cursor-pointer",
                hoveredSubject === s.id
                  ? "bg-sky-500/10 border-sky-500/25"
                  : "bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.04]"
              )}
              onMouseEnter={() => setHoveredSubject(s.id)}
              onMouseLeave={() => setHoveredSubject(null)}
            >
              <div className="flex justify-between items-center text-[0.65rem] mb-1">
                <span className="font-medium text-white/75">{s.name}</span>
                <span className="font-bold text-white/90">
                  {s.marks} <span className="text-emerald-400 ml-0.5">{s.grade}</span>
                </span>
              </div>
              <div className="h-1 w-full">
                <AnimatedBar width={s.pct} color={s.color} delay={400} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5 sm:p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <div className="p-1 rounded-md bg-emerald-500/10 text-emerald-400">
              <ShieldCheck className="size-3" />
            </div>
            <h5 className="text-[0.68rem] font-bold text-white/90">Risk &amp; Career</h5>
          </div>
          <span className="rounded-md border border-emerald-400/25 bg-emerald-500/10 px-1.5 py-px text-[0.6rem] font-medium text-emerald-400">
            Low Risk
          </span>
        </div>
        <div className="rounded-md bg-white/[0.03] border border-white/[0.05] px-2 py-1.5 mb-1.5">
          <div className="flex items-center justify-between text-[0.65rem] mb-1">
            <div className="flex items-center gap-1">
              <Briefcase className="size-3 text-sky-400" />
              <span className="font-medium text-white/75">AI/ML Engineer</span>
            </div>
            <span className="font-bold text-sky-400">82%</span>
          </div>
          <div className="h-1 w-full">
            <AnimatedBar width="82%" color="bg-gradient-to-r from-sky-400 to-emerald-400" delay={500} />
          </div>
        </div>
        <div className="flex items-start gap-1.5 rounded-md bg-sky-500/[0.06] border border-sky-500/15 px-2 py-1.5">
          <Sparkles className="size-3 text-sky-400 shrink-0 mt-px" />
          <span className="text-[0.62rem] text-white/55 leading-snug">
            <strong className="font-semibold text-sky-400">AI Guidance:</strong> Strong Python &amp; Algorithms.
          </span>
        </div>
      </div>
    </div>
  )
}

function M1v3TabPanel() {
  const subjects = [
    { name: "Data Mining (CS601)", marks: 61.5, grade: "AA", pct: "88%", color: "bg-emerald-400" },
    { name: "Machine Learning (CS602)", marks: 58.0, grade: "AB", pct: "83%", color: "bg-sky-400" },
    { name: "Cloud Computing (CS603)", marks: 55.5, grade: "AB", pct: "79%", color: "bg-sky-400" },
    { name: "Data Structures (CS604)", marks: 63.0, grade: "AA", pct: "90%", color: "bg-emerald-400" },
  ]
  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-200 space-y-1.5">
      {subjects.map((s) => (
        <div key={s.name} className="rounded-md p-2 border border-white/[0.04] bg-white/[0.02]">
          <div className="flex justify-between items-center text-[0.65rem] mb-1">
            <span className="font-medium text-white/75">{s.name}</span>
            <span className="font-bold text-white/90">
              {s.marks}/70 <span className="text-emerald-400 ml-0.5">{s.grade}</span>
            </span>
          </div>
          <div className="h-1 w-full">
            <AnimatedBar width={s.pct} color={s.color} delay={400} />
          </div>
        </div>
      ))}
    </div>
  )
}

function M3RiskTabPanel() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-200 space-y-1.5">
      <div className="rounded-md bg-white/[0.03] border border-white/[0.05] px-2 py-1.5">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[0.65rem] font-medium text-white/60">Risk Score</span>
          <span className="text-xs font-bold text-emerald-400">12%</span>
        </div>
        <div className="h-1 w-full">
          <AnimatedBar width="12%" color="bg-emerald-400" delay={300} />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <div className="rounded-md bg-emerald-500/[0.08] border border-emerald-500/20 px-2 py-1.5 text-center">
          <p className="text-[0.55rem] uppercase tracking-widest text-emerald-400/60 mb-0.5">Low</p>
          <p className="text-xs font-bold text-emerald-400">&#10003;</p>
        </div>
        <div className="rounded-md bg-white/[0.03] border border-white/[0.05] px-2 py-1.5 text-center">
          <p className="text-[0.55rem] uppercase tracking-widest text-white/30 mb-0.5">Med</p>
          <p className="text-xs font-bold text-white/20">&mdash;</p>
        </div>
        <div className="rounded-md bg-white/[0.03] border border-white/[0.05] px-2 py-1.5 text-center">
          <p className="text-[0.55rem] uppercase tracking-widest text-white/30 mb-0.5">High</p>
          <p className="text-xs font-bold text-white/20">&mdash;</p>
        </div>
      </div>
      <div className="rounded-md bg-emerald-500/[0.06] border border-emerald-500/15 px-2 py-1.5 flex items-start gap-1.5">
        <CheckCircle2 className="size-3 text-emerald-400 shrink-0 mt-px" />
        <span className="text-[0.62rem] text-white/55 leading-snug">
          <strong className="font-semibold text-emerald-400">Status:</strong> Low risk, consistent performance.
        </span>
      </div>
    </div>
  )
}

function M4CareerTabPanel() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-200 space-y-1.5">
      <div className="rounded-md bg-white/[0.03] border border-white/[0.05] px-2 py-1.5">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[0.65rem] font-medium text-white/60">Readiness Score</span>
          <span className="text-xs font-bold text-sky-400">78 / 100</span>
        </div>
        <div className="h-1 w-full">
          <AnimatedBar width="78%" color="bg-sky-400" delay={300} />
        </div>
      </div>
      <div className="rounded-md bg-white/[0.03] border border-white/[0.05] px-2 py-1.5">
        <div className="flex items-center gap-1 mb-1">
          <Briefcase className="size-3 text-sky-400" />
          <span className="text-[0.65rem] font-medium text-white/75">Target: AI/ML Engineer</span>
        </div>
        <div className="h-1 w-full">
          <AnimatedBar width="82%" color="bg-gradient-to-r from-sky-400 to-emerald-400" delay={400} />
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {["Python", "Algorithms", "Data Structures", "ML"].map((s) => (
          <span key={s} className="rounded border border-sky-400/20 bg-sky-500/10 px-1.5 py-px text-[0.58rem] font-medium text-sky-400">
            {s}
          </span>
        ))}
      </div>
      <div className="rounded-md bg-sky-500/[0.06] border border-sky-500/15 px-2 py-1.5 flex items-start gap-1.5">
        <Sparkles className="size-3 text-sky-400 shrink-0 mt-px" />
        <span className="text-[0.62rem] text-white/55 leading-snug">
          <strong className="font-semibold text-sky-400">Level:</strong> Strong — ready for AI/ML roles.
        </span>
      </div>
    </div>
  )
}

function TabContent({
  activeTab,
  hoveredSubject,
  setHoveredSubject,
}: {
  activeTab: TabKey
  hoveredSubject: string | null
  setHoveredSubject: (v: string | null) => void
}) {
  if (activeTab === "all") return <AllSignalsPanel hoveredSubject={hoveredSubject} setHoveredSubject={setHoveredSubject} />
  if (activeTab === "m1v3") return <M1v3TabPanel />
  if (activeTab === "m3-risk") return <M3RiskTabPanel />
  return <M4CareerTabPanel />
}

/* ── Main Preview ────────────────────────────────────────── */

export function DashboardPreview() {
  const [hoveredSubject, setHoveredSubject] = React.useState<string | null>(null)
  const [activeTab, setActiveTab] = React.useState<TabKey>("all")

  return (
    <div className="relative w-full rounded-xl border border-white/[0.08] bg-[#0c0f1a]/95 p-3 sm:p-4 shadow-[0_0_50px_-12px_rgba(56,189,248,0.12)] ring-1 ring-white/[0.05] backdrop-blur-2xl transition-all duration-300 hover:shadow-[0_0_60px_-12px_rgba(56,189,248,0.18)]">
      {/* Top ambient glow */}
      <div
        className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 w-2/3 h-12 bg-sky-500/10 blur-3xl rounded-full"
        aria-hidden="true"
      />

      {/* 1. Header Bar */}
      <div className="mb-3 flex items-center gap-2 border-b border-white/[0.06] pb-2.5">
        <div className="flex items-center gap-1">
          <span className="size-2 rounded-full bg-red-500/70" />
          <span className="size-2 rounded-full bg-yellow-500/70" />
          <span className="size-2 rounded-full bg-green-500/70" />
        </div>
        <span className="ml-1.5 text-[0.68rem] font-semibold tracking-wide text-white/90">
          CampusX Intelligence Console
        </span>
        <span className="ml-auto flex items-center gap-1.5 text-[0.6rem] text-emerald-400/70">
          <span className="relative flex size-1.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-emerald-400" />
          </span>
          Live
        </span>
      </div>

      {/* 2. Student Snapshot */}
      <div className="mb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5">
        <div className="flex items-center gap-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sky-500/15 border border-sky-500/25 text-sky-400 font-bold text-[0.65rem] shadow-sm">
            AP
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h4 className="text-[0.72rem] font-bold text-white/95">Aarav Patel</h4>
              <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 px-1.5 py-px text-[0.55rem] font-medium text-emerald-400">
                <CheckCircle2 className="size-2" />
                Good
              </span>
            </div>
            <p className="text-[0.6rem] text-white/35">B.Tech CS · Semester 6</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 self-stretch sm:self-auto justify-between sm:justify-end">
          <div className="rounded-md border border-white/[0.06] bg-white/[0.04] px-2 py-1.5 text-left sm:text-right">
            <p className="text-[0.5rem] font-semibold uppercase tracking-widest text-white/30">CGPA</p>
            <div className="flex items-baseline gap-1 sm:justify-end mt-0.5">
              <span className="text-xs sm:text-sm font-bold text-white/95">8.42</span>
              <span className="text-[0.55rem] font-semibold text-emerald-400 flex items-center">
                <TrendingUp className="size-2 mr-px" /> Top 5%
              </span>
            </div>
          </div>
          <div className="rounded-md border border-white/[0.06] bg-white/[0.04] px-2 py-1.5 text-left sm:text-right">
            <p className="text-[0.5rem] font-semibold uppercase tracking-widest text-white/30">Attendance</p>
            <div className="flex items-baseline gap-1 sm:justify-end mt-0.5">
              <span className="text-xs sm:text-sm font-bold text-emerald-400">88.4%</span>
              <span className="text-[0.55rem] text-white/30">On Track</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Tab Navigation + Tab Content */}
      <div>
        <div className="flex items-center gap-1 mb-2 overflow-x-auto scrollbar-none">
          {TAB_OPTIONS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "rounded-md px-2 py-1 text-[0.62rem] font-medium whitespace-nowrap transition-all",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400",
                activeTab === tab.key
                  ? "bg-sky-500/15 text-sky-400 border border-sky-400/25"
                  : "text-white/35 hover:text-white/55 hover:bg-white/[0.04] border border-transparent"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <TabContent activeTab={activeTab} hoveredSubject={hoveredSubject} setHoveredSubject={setHoveredSubject} />
      </div>
    </div>
  )
}
