import * as React from "react"
import Link from "next/link"

export function Footer() {
  return (
    <footer className="border-t border-border/60 bg-card/60 py-12 sm:py-16 text-muted-foreground">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          {/* Col 1: Brand & Mission */}
          <div className="md:col-span-1 space-y-3">
            <Link href="#top" className="flex items-center gap-2.5">
              <img
                src="/campusx-cx-icon.png"
                alt="CampusX"
                className="size-8 rounded-full object-contain"
              />
              <span className="text-base font-bold tracking-tight text-foreground">
                CampusX
              </span>
            </Link>
            <p className="text-xs text-muted-foreground leading-relaxed">
              AI-powered academic intelligence and student success platform unifying fragmented
              records, predictive analytics, and role-based portals.
            </p>

          </div>

          {/* Col 2: Navigation Links */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Navigation
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link href="#top" className="hover:text-foreground transition-colors">
                  Home
                </Link>
              </li>
              <li>
                <Link href="#features" className="hover:text-foreground transition-colors">
                  Platform Features
                </Link>
              </li>
              <li>
                <Link href="#intelligence" className="hover:text-foreground transition-colors">
                  AI & ML Models
                </Link>
              </li>
              <li>
                <Link href="#how-it-works" className="hover:text-foreground transition-colors">
                  How It Works
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 3: Role Portals */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Portals
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link href="/student/dashboard" className="hover:text-foreground transition-colors">
                  Student Portal
                </Link>
              </li>
              <li>
                <Link href="/faculty/dashboard" className="hover:text-foreground transition-colors">
                  Faculty Portal
                </Link>
              </li>
              <li>
                <Link href="/admin/dashboard" className="hover:text-foreground transition-colors">
                  Administrator Portal
                </Link>
              </li>
              <li>
                <Link href="/login" className="hover:text-foreground transition-colors">
                  Login
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 4: Platform Standards */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Architecture
            </h4>
            <ul className="space-y-2 text-xs">
              <li className="text-muted-foreground/80">Direct PostgreSQL Schemas</li>
              <li className="text-muted-foreground/80">Reload-Tested ML Pipelines</li>
              <li className="text-muted-foreground/80">Grounded GenAI Boundaries</li>
              <li className="text-muted-foreground/80">HttpOnly Session Security</li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-border/40 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
          <p className="text-muted-foreground">
            &copy; {new Date().getFullYear()} CampusX. All rights reserved. Academic intelligence platform.
          </p>

          <div className="flex items-center gap-6">
            <span className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
              Privacy Policy
            </span>
            <span className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
              Terms of Service
            </span>
            <span className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
              Academic Governance
            </span>
          </div>
        </div>
      </div>
    </footer>
  )
}
