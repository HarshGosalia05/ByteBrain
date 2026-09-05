import { Pool } from "pg"

const globalForPg = globalThis as unknown as { pgPool?: Pool }

const pool =
  globalForPg.pgPool ??
  new Pool({
    connectionString:
      process.env.DATABASE_URL ||
      (process.env.DB_USER
        ? `postgresql://${process.env.DB_USER}:${encodeURIComponent(process.env.DB_PASSWORD || "")}@${process.env.DB_HOST || "localhost"}:${process.env.DB_PORT || "5432"}/${process.env.DB_NAME || ""}`
        : undefined),
    ssl:
      process.env.DB_SSL_REJECT_UNAUTHORIZED === "false"
        ? { rejectUnauthorized: false }
        : process.env.DB_HOST?.includes("supabase") ||
            process.env.DB_PORT === "6543"
          ? { rejectUnauthorized: false }
          : undefined,
    connectionTimeoutMillis: 10000,
    max: 5,
    idleTimeoutMillis: 30000,
  })

if (process.env.NODE_ENV !== "production") {
  globalForPg.pgPool = pool
}

export async function query(text: string, params?: unknown[]) {
  const client = await pool.connect()
  try {
    const result = await client.query(text, params)
    return result
  } finally {
    client.release()
  }
}

