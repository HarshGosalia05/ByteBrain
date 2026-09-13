import * as React from "react"
import Link from "next/link"
import {
  ArrowRight,
  CheckCircle2,
  GraduationCap,
  School,
  UserCheck,
} from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface RolesSectionProps {
  userRole?: string | null
}

export function RolesSection({ userRole }: RolesSectionProps) {
  const isAuth = Boolean(userRole)

  return (
    <section id="roles" className="py-20 sm:py-28 relative">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <Badge variant="outline" className="mb-3 text-xs tracking-wider uppercase">
            Built For Every Stakeholder
          </Badge>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Role-Tailored Intelligence Across Campus
          </h2>
          <p className="mt-4 text-base sm:text-lg text-muted-foreground">
            CampusX delivers tailored workspaces with strict data boundaries, ensuring each
            stakeholder gets the precise insights, tools, and actions they need.
          </p>
        </div>

        {/* 3 Role Cards Grid with Dynamic Auth / Role Destination */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 1. Student Card */}
          <div
            id="students"
            className={cn(
              "group relative flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 sm:p-8 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-primary hover:shadow-xl ring-1 ring-foreground/5",
              userRole?.toLowerCase() === "student" && "border-primary ring-2 ring-primary/30"
            )}
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-all duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground group-hover:shadow-md">
                  <GraduationCap className="size-6" />
                </span>
                <span className="text-xs font-semibold text-primary uppercase tracking-wider bg-primary/10 px-2.5 py-0.5 rounded-full border border-primary/20">
                  Students {userRole?.toLowerCase() === "student" ? "• Active" : ""}
                </span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold text-foreground group-hover:text-primary transition-colors">
                For Students
              </h3>
              <p className="text-xs font-medium text-primary mt-0.5">
                &ldquo;Know where you stand.&rdquo;
              </p>

              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                Understand your academic performance, monitor attendance, explore
                subject insights, assess academic risk, and prepare for your career.
              </p>

              <div className="mt-6 pt-6 border-t border-border/60">
                <p className="text-xs font-semibold uppercase tracking-wider text-foreground mb-3">
                  Core Capabilities
                </p>
                <ul className="space-y-2.5">
                  {[
                    "Academic Dashboard (CGPA/SGPA progression)",
                    "Subject Insights (continuous evaluation tracking)",
                    "Attendance Monitoring & defaulter warnings",
                    "ML Insights (M1_v3 marks & M3 risk analysis)",
                    "Career Guidance (readiness & dream role match)",
                    "Real-time Academic Notifications",
                  ].map((feat) => (
                    <li key={feat} className="flex items-start gap-2 text-xs text-muted-foreground group-hover:text-foreground/90 transition-colors">
                      <CheckCircle2 className="size-4 text-chart-2 shrink-0 mt-0.5 transition-transform duration-200 group-hover:scale-110" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-8 pt-4">
              <Link
                href={isAuth ? "/student/dashboard" : "/login?role=student"}
                className={cn(
                  buttonVariants({ variant: "outline" }),
                  "w-full justify-between gap-2 group-hover:border-primary group-hover:bg-primary/10 transition-all duration-200"
                )}
              >
                <span>{isAuth ? "Explore Student Portal" : "Login as Student"}</span>
                <ArrowRight className="size-4 text-primary transition-transform duration-200 group-hover:translate-x-1" />
              </Link>
            </div>
          </div>

          {/* 2. Faculty Card */}
          <div
            id="faculty"
            className={cn(
              "group relative flex flex-col justify-between rounded-2xl border border-primary/40 bg-card p-6 sm:p-8 shadow-md transition-all duration-300 hover:-translate-y-1 hover:border-primary hover:shadow-xl ring-1 ring-primary/20",
              userRole?.toLowerCase() === "faculty" && "ring-2 ring-primary border-primary"
            )}
          >
            {/* Top highlight indicator */}
            {/* <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <span className="inline-block rounded-full bg-primary px-3.5 py-0.5 text-[0.65rem] font-bold text-primary-foreground uppercase tracking-wider shadow-sm">
                Comprehensive Command Center
              </span>
            </div> */}

            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-all duration-300 group-hover:scale-110 group-hover:shadow-md">
                  <UserCheck className="size-6" />
                </span>
                <span className="text-xs font-semibold text-primary uppercase tracking-wider bg-primary/10 px-2.5 py-0.5 rounded-full border border-primary/20">
                  Faculty {userRole?.toLowerCase() === "faculty" ? "• Active" : ""}
                </span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold text-foreground group-hover:text-primary transition-colors">
                For Faculty
              </h3>
              <p className="text-xs font-medium text-primary mt-0.5">
                &ldquo;Know who needs attention.&rdquo;
              </p>

              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                Monitor students, understand academic performance, analyze
                attendance and subjects, and make data-informed decisions.
              </p>

              <div className="mt-6 pt-6 border-t border-border/60">
                <p className="text-xs font-semibold uppercase tracking-wider text-foreground mb-3">
                  Core Capabilities
                </p>
                <ul className="space-y-2.5">
                  {[
                    "Student Management & mentee cohorts",
                    "Performance Analytics (learning gaps & grade curves)",
                    "Attendance Analytics (heatmaps & defaulter review)",
                    "Subject Analytics & marks management",
                    "Teaching Workload (capacity & governance score)",
                    "Faculty Insights & alert dispatch",
                  ].map((feat) => (
                    <li key={feat} className="flex items-start gap-2 text-xs text-muted-foreground group-hover:text-foreground/90 transition-colors">
                      <CheckCircle2 className="size-4 text-primary shrink-0 mt-0.5 transition-transform duration-200 group-hover:scale-110" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-8 pt-4">
              <Link
                href={isAuth ? "/faculty/dashboard" : "/login?role=faculty"}
                className={cn(
                  buttonVariants(),
                  "w-full justify-between gap-2 shadow-xs transition-all duration-200 hover:shadow-md"
                )}
              >
                <span>{isAuth ? "Explore Faculty Portal" : "Login as Faculty"}</span>
                <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-1" />
              </Link>
            </div>
          </div>

          {/* 3. Administrator Card */}
          <div
            id="admins"
            className={cn(
              "group relative flex flex-col justify-between rounded-2xl border border-border/80 bg-card p-6 sm:p-8 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-primary hover:shadow-xl ring-1 ring-foreground/5",
              userRole?.toLowerCase() === "admin" && "border-primary ring-2 ring-primary/30"
            )}
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-all duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground group-hover:shadow-md">
                  <School className="size-6" />
                </span>
                <span className="text-xs font-semibold text-primary uppercase tracking-wider bg-primary/10 px-2.5 py-0.5 rounded-full border border-primary/20">
                  Administrators {userRole?.toLowerCase() === "admin" ? "• Active" : ""}
                </span>
              </div>

              <h3 className="text-xl sm:text-2xl font-bold text-foreground group-hover:text-primary transition-colors">
                For Administrators
              </h3>
              <p className="text-xs font-medium text-primary mt-0.5">
                &ldquo;Know what is happening across the institution.&rdquo;
              </p>

              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                Manage academic operations and understand institution-wide
                performance through centralized analytics.
              </p>

              <div className="mt-6 pt-6 border-t border-border/60">
                <p className="text-xs font-semibold uppercase tracking-wider text-foreground mb-3">
                  Core Capabilities
                </p>
                <ul className="space-y-2.5">
                  {[
                    "Institution Analytics (department comparisons)",
                    "Student Analytics (cohort retention & trajectories)",
                    "Faculty Analytics (department workload balance)",
                    "Academic Intelligence (institution-wide risk)",
                    "Standardized Reports & 30+ CSV data exports",
                    "Campus Announcements & governance controls",
                  ].map((feat) => (
                    <li key={feat} className="flex items-start gap-2 text-xs text-muted-foreground group-hover:text-foreground/90 transition-colors">
                      <CheckCircle2 className="size-4 text-chart-2 shrink-0 mt-0.5 transition-transform duration-200 group-hover:scale-110" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-8 pt-4">
              <Link
                href={isAuth ? "/admin/dashboard" : "/login?role=admin"}
                className={cn(
                  buttonVariants({ variant: "outline" }),
                  "w-full justify-between gap-2 group-hover:border-primary group-hover:bg-primary/10 transition-all duration-200"
                )}
              >
                <span>{isAuth ? "Explore Admin Portal" : "Login as Admin"}</span>
                <ArrowRight className="size-4 text-primary transition-transform duration-200 group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
