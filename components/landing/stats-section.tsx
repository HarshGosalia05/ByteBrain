import * as React from "react"
import { BarChart3, Database, Layers, ShieldCheck, Users } from "lucide-react"

const STATS = [
  {
    icon: Users,
    value: "3",
    label: "Dedicated Portals",
    description: "Role-scoped for Students, Faculty, and Admins",
  },
  {
    icon: Database,
    value: "21+",
    label: "Database Tables",
    description: "7 unified domains in Supabase PostgreSQL",
  },
  {
    icon: Layers,
    value: "5",
    label: "Academic Models",
    description: "M1_v3, M2-TP, M3, M4 & M5 pipelines",
  },
  {
    icon: BarChart3,
    value: "39+",
    label: "Analytics Views",
    description: "Real-time trends, heatmaps & workload gauges",
  },
  {
    icon: ShieldCheck,
    value: "100%",
    label: "Grounded Insights",
    description: "Strict RBAC, audit logs & zero data leakage",
  },
]

export function StatsSection() {
  return (
    <section className="relative border-y border-border/60 bg-muted/20 py-10 sm:py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 sm:gap-8">
          {STATS.map((stat) => {
            const Icon = stat.icon
            return (
              <div
                key={stat.label}
                className="flex flex-col items-center text-center p-3 rounded-xl transition-colors hover:bg-card/50"
              >
                <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-4" />
                </div>
                <span className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground tabular-nums">
                  {stat.value}
                </span>
                <span className="mt-1 text-sm font-semibold text-foreground">
                  {stat.label}
                </span>
                <p className="mt-0.5 text-xs text-muted-foreground leading-snug">
                  {stat.description}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
