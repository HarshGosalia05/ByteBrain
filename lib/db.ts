import { Pool } from "pg"

const globalForPg = globalThis as unknown as { pgPool?: Pool }

const pool =
  globalForPg.pgPool ??
  new Pool({
    connectionString: `postgresql://${process.env.DB_USER}:${encodeURIComponent(process.env.DB_PASSWORD!)}@${process.env.DB_HOST}:${process.env.DB_PORT}/${process.env.DB_NAME}`,
    ssl: { rejectUnauthorized: false },
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

