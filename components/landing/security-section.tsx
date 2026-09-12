import * as React from "react"
import {
  Database,
  EyeOff,
  KeyRound,
  Server,
  ShieldCheck,
  UserCheck,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"

const TRUST_PILLARS = [
  {
    icon: UserCheck,
    title: "Role-Based Access Control",
    desc: "Strict authorization walls isolate student personal data from unauthorized peers and restrict administrative actions to verified staff.",
  },
  {
    icon: Database,
    title: "Verified Institutional Data",
    desc: "Direct PostgreSQL connections via asyncpg eliminate fragile client-side queries and ensure single-source data veracity.",
  },
  {
    icon: KeyRound,
    title: "HttpOnly Cookie Sessions",
    desc: "HMAC-SHA256 signed session tokens stored in secure, tamper-resistant cookies eliminate client-side token exposure.",
  },
  {
    icon: EyeOff,
    title: "Student Data Privacy",
    desc: "FERPA-aligned data segregation guarantees that performance records, lifestyle surveys, and predictions remain strictly confidential.",
  },
  {
    icon: ShieldCheck,
    title: "Controlled AI Context",
    desc: "Generative AI calls are sanitized through strict prompt grounding templates with zero training on proprietary institutional data.",
  },
  {
    icon: Server,
    title: "Institution Governance & Audit",
    desc: "Comprehensive change logs capture attendance adjustments, marks entries, and model prediction requests for institutional auditability.",
  },
]

export function SecuritySection() {
  return (
    <section className="py-20 sm:py-28 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            Security & Governance
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Enterprise Trust & Data Integrity
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            Built from the ground up to protect academic records, ensure strict role compliance,
            and maintain an uncompromised audit trail across all campus departments.
          </p>
        </div>

        {/* 6 Security Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {TRUST_PILLARS.map((pillar) => {
            const Icon = pillar.icon
            return (
              <div
                key={pillar.title}
                className="flex flex-col rounded-2xl border border-border/80 bg-card p-6 shadow-xs ring-1 ring-foreground/5 hover:border-primary/40 transition-colors"
              >
                <div className="mb-4 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <h3 className="text-base font-bold text-foreground">
                  {pillar.title}
                </h3>
                <p className="mt-2 text-xs sm:text-sm text-muted-foreground leading-relaxed">
                  {pillar.desc}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
