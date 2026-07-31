import { readFileSync, readdirSync } from "fs"
import { join } from "path"
import { query } from "@/lib/db"

export async function GET() {
  const results: Record<string, unknown>[] = []

  const migrationsDir = join(process.cwd(), "migrations")
  const files = readdirSync(migrationsDir).sort()

  for (const file of files) {
    if (!file.endsWith(".sql")) continue
    const sql = readFileSync(join(migrationsDir, file), "utf-8")
    try {
      await query(sql)
      results.push({ step: file, ok: true })
    } catch (e) {
      const msg = String(e)
      results.push({
        step: file,
        ok: msg.includes("duplicate") ? "already-seeded" : false,
        error: msg.includes("duplicate") ? "skipped (duplicate)" : msg.slice(0, 120),
      })
    }
  }

  const { rows: userCount } = await query("SELECT COUNT(*) as cnt FROM users")
  results.push({ step: "users-count", count: userCount[0]?.cnt })

  return Response.json(results)
}

export const dynamic = "force-dynamic"
