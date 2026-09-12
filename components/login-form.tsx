"use client"

import * as React from "react"
import Link from "next/link"
import { useActionState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  GraduationCap,
  Lock,
  School,
  TriangleAlert,
  User,
  UserCheck,
} from "lucide-react"

import { login } from "@/app/login/actions"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export type LoginRole = "student" | "faculty" | "admin"

interface LoginFormProps extends React.ComponentProps<"div"> {
  initialRole?: string | null
}

const ROLE_CONFIGS: Record<
  LoginRole,
  {
    role: LoginRole
    title: string
    portal: string
    description: string
    icon: React.ComponentType<{ className?: string }>
    usernamePlaceholder: string
  }
> = {
  student: {
    role: "student",
    title: "Student Login",
    portal: "Student Portal",
    description: "Access your academic intelligence dashboard, attendance, and ML predictions.",
    icon: GraduationCap,
    usernamePlaceholder: "Enter your student username or enrollment no",
  },
  faculty: {
    role: "faculty",
    title: "Faculty Login",
    portal: "Faculty Portal",
    description: "Manage courses, monitor student cohorts, and analyze teaching workload.",
    icon: UserCheck,
    usernamePlaceholder: "Enter your faculty username or ID",
  },
  admin: {
    role: "admin",
    title: "Admin Login",
    portal: "Administrator Portal",
    description: "Oversee institutional analytics, departments, and academic governance.",
    icon: School,
    usernamePlaceholder: "Enter your administrator username",
  },
}

function normalizeRole(roleStr?: string | null): LoginRole | null {
  if (!roleStr) return null
  const lower = roleStr.trim().toLowerCase()
  if (lower === "student") return "student"
  if (lower === "faculty") return "faculty"
  if (lower === "admin" || lower === "administrator") return "admin"
  return null
}

export function LoginForm({ initialRole, className, ...props }: LoginFormProps) {
  const [selectedRole, setSelectedRole] = React.useState<LoginRole | null>(() =>
    normalizeRole(initialRole)
  )
  const [showPassword, setShowPassword] = React.useState(false)
  const [state, formAction, pending] = useActionState(login, undefined)

  const selectRole = (role: LoginRole) => {
    setSelectedRole(role)
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href)
      url.searchParams.set("role", role)
      window.history.pushState({}, "", url.toString())
    }
  }

  const clearRole = () => {
    setSelectedRole(null)
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href)
      url.searchParams.delete("role")
      window.history.pushState({}, "", url.toString())
    }
  }

  // SCREEN 1: Role Selection Screen (when no role is chosen)
  if (!selectedRole) {
    return (
      <div className={cn("flex flex-col gap-6", className)} {...props}>
        <Card className="border-border/80 bg-card/95 shadow-2xl ring-1 ring-foreground/5 backdrop-blur-md">
          <CardHeader className="text-center pb-4">
            <img
              src="/campusx-cx-icon.png"
              alt="CampusX"
              className="mx-auto size-12 rounded-2xl object-contain shadow-md mb-3"
            />
            <CardTitle className="text-2xl font-extrabold tracking-tight text-foreground">
              Welcome to CampusX
            </CardTitle>
            <CardDescription className="text-sm text-muted-foreground mt-1">
              Choose your portal to continue
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-3 pt-2">
            {(["student", "faculty", "admin"] as const).map((r) => {
              const cfg = ROLE_CONFIGS[r]
              const Icon = cfg.icon
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => selectRole(r)}
                  className="w-full flex items-center justify-between p-4 rounded-xl border border-border/70 bg-muted/20 hover:border-primary hover:bg-muted/40 hover:-translate-y-0.5 transition-all duration-200 text-left group cursor-pointer ring-1 ring-foreground/5"
                >
                  <div className="flex items-center gap-3.5">
                    <span className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary transition-all duration-200 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground group-hover:shadow-sm">
                      <Icon className="size-5" />
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                        {cfg.portal}
                      </h3>
                      <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                        {cfg.description}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground transition-transform duration-200 group-hover:text-primary group-hover:translate-x-1 shrink-0 ml-2" />
                </button>
              )
            })}

            <div className="pt-4 text-center border-t border-border/40">
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="size-3.5" />
                <span>Back to CampusX Home</span>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // SCREEN 2: Role-Specific Login Form
  const config = ROLE_CONFIGS[selectedRole]
  const Icon = config.icon

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card className="border-border/80 bg-card/95 shadow-2xl ring-1 ring-foreground/5 backdrop-blur-md">
        <CardHeader className="space-y-3 pb-4">
          {/* Top Switcher Navigation */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={clearRole}
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <ArrowLeft className="size-3.5" />
              <span>All Portals</span>
            </button>

            {/* Role Switcher Pills */}
            <div className="flex items-center gap-1 rounded-lg bg-muted/40 p-1 border border-border/40">
              {(["student", "faculty", "admin"] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => selectRole(r)}
                  className={cn(
                    "rounded-md px-2.5 py-0.5 text-xs font-medium capitalize transition-all cursor-pointer",
                    selectedRole === r
                      ? "bg-primary text-primary-foreground shadow-xs font-semibold"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Role Header */}
          <div className="flex items-center gap-3 pt-2">
            <span className="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
              <Icon className="size-5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-xl font-bold text-foreground">
                  {config.title}
                </CardTitle>
              </div>
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                {config.portal}
              </span>
            </div>
          </div>

          <CardDescription className="text-xs text-muted-foreground leading-relaxed">
            {config.description}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form action={formAction} className="space-y-4">
            {/* Hidden Expected Role */}
            <input type="hidden" name="expected_role" value={selectedRole} />

            {/* Username / ID Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="username"
                className="text-xs font-semibold text-foreground flex items-center justify-between"
              >
                <span>Username or Enrollment ID</span>
                <span className="text-[0.65rem] text-muted-foreground">Required</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  <User className="size-4" />
                </span>
                <Input
                  id="username"
                  name="username"
                  type="text"
                  placeholder={config.usernamePlaceholder}
                  className="pl-9 text-sm"
                  required
                  autoFocus
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="text-xs font-semibold text-foreground flex items-center justify-between"
              >
                <span>Password</span>
                <span className="text-[0.65rem] text-muted-foreground">Required</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  <Lock className="size-4" />
                </span>
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your account password"
                  className="pl-9 pr-9 text-sm"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            {/* Error Message Display */}
            {state?.error && (
              <div className="flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive animate-in fade-in duration-150">
                <TriangleAlert className="size-4 shrink-0 mt-0.5" />
                <span>{state.error}</span>
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={pending}
              className="w-full justify-center gap-2 py-5 text-sm font-semibold shadow-xs transition-transform duration-150 active:scale-[0.99]"
            >
              {pending ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>Login to {config.portal}</span>
                  <ArrowRight className="size-4" />
                </>
              )}
            </Button>
          </form>

          {/* Footer Back Link */}
          <div className="mt-6 pt-4 text-center border-t border-border/40">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="size-3.5" />
              <span>Back to CampusX Home</span>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
