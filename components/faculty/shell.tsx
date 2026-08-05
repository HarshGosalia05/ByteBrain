"use client"

import * as React from "react"
import Link from "next/link"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { SideNav } from "@/components/faculty/side-nav"
import { TopBar } from "@/components/faculty/top-bar"
import type { FacultyProfile } from "@/lib/faculty-api"

function Brand() {
  return (
    <Link href="/faculty/dashboard" className="flex items-center gap-2 px-1">
      <span className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
        K
      </span>
      <span className="text-sm font-semibold">KenexAI</span>
    </Link>
  )
}

export function FacultyShell({
  children,
  profile,
}: {
  children: React.ReactNode
  profile: FacultyProfile | null
}) {
  const [open, setOpen] = React.useState(false)
  const closeButtonRef = React.useRef<HTMLButtonElement>(null)

  React.useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKeyDown)
    closeButtonRef.current?.focus()
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [open])

  React.useEffect(() => {
    if (!open) return
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  return (
    <div className="flex min-h-svh">
      <aside className="hidden lg:sticky lg:top-0 lg:flex lg:h-svh lg:w-64 lg:shrink-0 lg:flex-col lg:gap-6 lg:border-r lg:border-sidebar-border lg:bg-sidebar lg:px-4 lg:py-6 print:hidden">
        <Brand />
        <SideNav />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="print:hidden">
          <TopBar menuOpen={open} onMenu={() => setOpen(true)} profile={profile} />
        </div>
        <main className="flex-1 px-4 py-6 lg:px-8 print:p-0">{children}</main>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <div
            className="absolute inset-0 bg-background/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col gap-6 border-r border-sidebar-border bg-sidebar px-4 py-6 shadow-xl">
            <div className="flex items-center justify-between">
              <Brand />
              <Button
                ref={closeButtonRef}
                variant="ghost"
                size="icon"
                aria-label="Close navigation menu"
                onClick={() => setOpen(false)}
              >
                <X className="size-4" />
              </Button>
            </div>
            <SideNav />
          </div>
        </div>
      )}
    </div>
  )
}
