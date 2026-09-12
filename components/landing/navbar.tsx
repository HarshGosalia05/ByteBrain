"use client"

import * as React from "react"
import Link from "next/link"
import { Menu, Moon, Sun, X, ArrowRight, LayoutDashboard } from "lucide-react"
import { useTheme } from "next-themes"

import { Button, buttonVariants } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface NavbarProps {
  userRole?: string | null
  dashboardUrl?: string | null
}

const NAV_LINKS = [
  { label: "Home", href: "#top" },
  { label: "Features", href: "#features" },
  { label: "For Students", href: "#students" },
  { label: "For Faculty", href: "#faculty" },
  { label: "For Admins", href: "#admins" },
  { label: "AI Insights", href: "#intelligence" },
  { label: "About", href: "#how-it-works" },
]

function emptySubscribe() {
  return () => {}
}

export function Navbar({ userRole, dashboardUrl }: NavbarProps) {
  const [scrolled, setScrolled] = React.useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false)
  const mounted = React.useSyncExternalStore(emptySubscribe, () => true, () => false)
  const { resolvedTheme, setTheme } = useTheme()

  React.useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }
    window.addEventListener("scroll", handleScroll, { passive: true })
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  // Lock body scroll when mobile menu is open
  React.useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [mobileMenuOpen])

  // Close on Escape
  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.startsWith("#")) {
      e.preventDefault()
      const targetId = href.replace("#", "")
      const target = document.getElementById(targetId)
      if (target) {
        target.scrollIntoView({ behavior: "smooth" })
        window.history.pushState(null, "", href)
      } else if (href === "#top") {
        window.scrollTo({ top: 0, behavior: "smooth" })
      }
      setMobileMenuOpen(false)
    }
  }

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full transition-all duration-300",
        scrolled
          ? "border-b border-border/60 bg-background/90 py-2.5 backdrop-blur-md shadow-xs"
          : "border-b border-transparent bg-background/50 py-4 backdrop-blur-xs"
      )}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo */}
        <Link
          href="#top"
          onClick={(e) => handleNavClick(e, "#top")}
          className="group flex items-center gap-2.5 outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-lg p-1"
          aria-label="CampusX Home"
        >
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-foreground shadow-sm transition-transform duration-200 group-hover:scale-105">
            K
          </span>
          <span className="text-base font-semibold tracking-tight text-foreground">
            CampusX
          </span>
        </Link>

        {/* Desktop Navigation Links */}
        <nav
          className="hidden md:flex items-center gap-1 lg:gap-1.5"
          aria-label="Main Navigation"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={(e) => handleNavClick(e, link.href)}
              className="rounded-lg px-3 py-1.5 text-xs lg:text-sm font-medium text-muted-foreground transition-all duration-150 hover:text-foreground hover:bg-accent/60 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Right Actions: Theme Toggle & Login / Get Started */}
        <div className="flex items-center gap-2">
          {/* Theme Toggle Button */}
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle theme"
            className="text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          >
            {mounted ? (
              resolvedTheme === "dark" ? (
                <Sun className="size-4" />
              ) : (
                <Moon className="size-4" />
              )
            ) : (
              <span className="size-4" />
            )}
          </Button>

          {/* Auth-Aware CTA Group */}
          {dashboardUrl ? (
            <div className="flex items-center gap-2">
              {userRole && (
                <Badge variant="outline" className="hidden sm:inline-flex text-xs capitalize border-primary/30 text-primary">
                  {userRole}
                </Badge>
              )}
              <Link
                href={dashboardUrl}
                className={cn(buttonVariants({ size: "sm" }), "gap-1.5 transition-transform duration-150 hover:scale-105 active:scale-95")}
              >
                <LayoutDashboard className="size-3.5" />
                <span>Go to Dashboard</span>
              </Link>
            </div>
          ) : (
            <div className="hidden sm:flex items-center gap-2">
              <Link
                href="/login"
                className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "text-muted-foreground hover:text-foreground transition-colors")}
              >
                Login
              </Link>
              <Link
                href="/login"
                className={cn(
                  buttonVariants({ size: "sm" }),
                  "gap-1.5 font-medium shadow-xs transition-all duration-150 hover:scale-105 active:scale-95"
                )}
              >
                <span>Get Started</span>
                <ArrowRight className="size-3.5" />
              </Link>
            </div>
          )}

          {/* Mobile Menu Button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden text-foreground"
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 top-[57px] z-50 flex flex-col bg-background/95 backdrop-blur-md p-6 md:hidden border-b border-border animate-in fade-in slide-in-from-top-4 duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile Navigation Menu"
        >
          <div className="flex flex-col gap-2">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={(e) => handleNavClick(e, link.href)}
                className="rounded-lg px-4 py-3 text-base font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                {link.label}
              </Link>
            ))}
          </div>

          <div className="mt-auto border-t border-border pt-6 flex flex-col gap-3">
            {dashboardUrl ? (
              <Link
                href={dashboardUrl}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(buttonVariants({ size: "lg" }), "w-full justify-center gap-2")}
              >
                <LayoutDashboard className="size-4" />
                <span>Go to {userRole ?? "User"} Dashboard</span>
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(buttonVariants({ variant: "outline", size: "lg" }), "w-full justify-center")}
                >
                  Login
                </Link>
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(buttonVariants({ size: "lg" }), "w-full justify-center gap-2")}
                >
                  <span>Get Started</span>
                  <ArrowRight className="size-4" />
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  )
}
