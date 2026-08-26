"""Inspect the live Supabase PostgreSQL schema via the ETL db pool."""

import asyncio
import json

from etl.db import create_pool


async def main():
    pool = await create_pool()

    async with pool.acquire() as conn:
        # 1. Discover all public tables
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        table_names = [r["tablename"] for r in tables]
        print(f"Found {len(table_names)} public tables: {table_names}")

        result = {}

        for tname in table_names:
            print(f"\n--- Inspecting {tname} ---")
            entry = {}

            # Columns
            cols = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                tname,
            )
            entry["columns"] = [
                {
                    "column_name": c["column_name"],
                    "data_type": c["data_type"],
                    "is_nullable": c["is_nullable"],
                    "column_default": c["column_default"],
                }
                for c in cols
            ]

            # Primary keys
            pks = await conn.fetch(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = $1
                ORDER BY kcu.ordinal_position
                """,
                tname,
            )
            entry["primary_keys"] = [r["column_name"] for r in pks]

            # Foreign keys
            fks = await conn.fetch(
                """
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = $1
                """,
                tname,
            )
            entry["foreign_keys"] = [
                {
                    "constraint_name": r["constraint_name"],
                    "column": r["column_name"],
                    "foreign_table": r["foreign_table"],
                    "foreign_column": r["foreign_column"],
                }
                for r in fks
            ]

            # Check constraints
            checks = await conn.fetch(
                """
                SELECT tc.constraint_name, pg_get_constraintdef(c.oid) AS definition
                FROM information_schema.table_constraints tc
                JOIN pg_class pgc ON pgc.relname = tc.table_name
                  AND pgc.relnamespace = 'public'::regnamespace
                JOIN pg_constraint c
                  ON c.conname = tc.constraint_name
                  AND c.conrelid = pgc.oid
                WHERE tc.constraint_type = 'CHECK'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = $1
                """,
                tname,
            )
            entry["check_constraints"] = [
                {"constraint_name": r["constraint_name"], "definition": r["definition"]}
                for r in checks
            ]

            # Indexes
            indexes = await conn.fetch(
                """
                SELECT
                    ixcls.relname AS index_name,
                    am.amname AS index_type,
                    array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns,
                    ix.indisunique AS is_unique
                FROM pg_index ix
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_class ixcls ON ixcls.oid = ix.indexrelid
                JOIN pg_am am ON am.oid = ixcls.relam
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE n.nspname = 'public' AND t.relname = $1
                GROUP BY ixcls.relname, ix.indexrelid, ix.indrelid, am.amname, ix.indisunique
                ORDER BY ixcls.relname
                """,
                tname,
            )
            entry["indexes"] = [
                {
                    "index_name": r["index_name"],
                    "index_type": r["index_type"],
                    "columns": r["columns"],
                    "is_unique": r["is_unique"],
                }
                for r in indexes
            ]

            # Row count
            rc = await conn.fetchval(f'SELECT count(*) FROM "{tname}"')
            entry["row_count"] = rc
            print(f"  rows: {rc}")

            # Sample row + value ranges (for tables with data)
            if rc and rc > 0:
                # Sample row
                sample = await conn.fetchrow(f'SELECT * FROM "{tname}" LIMIT 1')
                entry["sample_row"] = {k: _serialize(v) for k, v in dict(sample).items()}

                # Value ranges for numeric columns and distinct values for low-cardinality text
                col_names = [c["column_name"] for c in cols]
                col_types = {c["column_name"]: c["data_type"] for c in cols}

                value_ranges = {}
                for cname in col_names:
                    ctype = col_types[cname]
                    if ctype in ("integer", "bigint", "smallint", "numeric", "real", "double precision", "decimal"):
                        try:
                            rng = await conn.fetchrow(
                                f'SELECT min("{cname}") AS min_val, max("{cname}") AS max_val FROM "{tname}" WHERE "{cname}" IS NOT NULL'
                            )
                            value_ranges[cname] = {"type": "numeric", "min": _serialize(rng["min_val"]), "max": _serialize(rng["max_val"])}
                        except Exception:
                            pass
                    elif ctype in ("text", "varchar", "character varying", "char", "character"):
                        try:
                            distinct = await conn.fetch(
                                f'SELECT DISTINCT "{cname}" FROM "{tname}" WHERE "{cname}" IS NOT NULL LIMIT 50'
                            )
                            vals = [r[0] for r in distinct]
                            if len(vals) <= 50:
                                value_ranges[cname] = {"type": "text_distinct", "distinct_count": len(vals), "values": vals}
                            else:
                                value_ranges[cname] = {"type": "text_distinct", "distinct_count": len(vals), "values_sample": vals}
                        except Exception:
                            pass

                entry["value_ranges"] = value_ranges

            result[tname] = entry

    # Save
    out_path = "D:\\KenexAi\\ByteBrain\\backend\\db_schema_inspect.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSaved schema to {out_path}")

    await pool.close()


def _serialize(val):
    """Make values JSON-safe."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


if __name__ == "__main__":
    asyncio.run(main())
