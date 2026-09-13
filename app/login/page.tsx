import type { Metadata } from "next"
import { LoginForm } from "@/components/login-form"
import { SplashCursor } from "@/components/landing/splash-cursor"

interface LoginPageProps {
  searchParams: Promise<{ role?: string }>
}

export const metadata: Metadata = {
  title: "Login — CampusX Academic Intelligence",
  description:
    "Secure role-scoped login portal for Students, Faculty, and Administrators in CampusX.",
}

export default async function LoginPage(props: LoginPageProps) {
  const searchParams = await props.searchParams
  const role = typeof searchParams.role === "string" ? searchParams.role : null

  return (
    <div className="flex min-h-svh w-full items-center justify-center p-4 sm:p-6 md:p-10 bg-background text-foreground relative overflow-hidden">
      {/* Background Interactive Splash Cursor (same as Home page) */}
      <SplashCursor
        COLOR="#1da1f2"
        RAINBOW_MODE={false}
        SPLAT_FORCE={1800}
        SPLAT_RADIUS={0.14}
        DENSITY_DISSIPATION={4.5}
        VELOCITY_DISSIPATION={2.5}
        CURL={1.5}
      />

      {/* Ambient subtle glow background */}
      <div
        className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[300px] bg-primary/10 blur-[130px] rounded-full -z-10"
        aria-hidden="true"
      />
      <div className="w-full max-w-md relative z-10">
        <LoginForm key={role ?? "chooser"} initialRole={role} />
      </div>
    </div>
  )
}
