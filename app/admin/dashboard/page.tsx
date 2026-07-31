import { requireRole } from "@/lib/session"

export default async function Page() {
  await requireRole("Admin")

  return (
    <main className="flex min-h-svh items-center justify-center">
      <h1 className="text-2xl font-medium">Welcome to Admin Dashboard</h1>
    </main>
  )
}
