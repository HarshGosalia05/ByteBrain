import psycopg2
import pandas as pd
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from db_env import db_config  # noqa: E402

DB = db_config()
DB_HOST = DB.host
DB_PORT = DB.port
DB_NAME = DB.name
DB_USER = DB.user
DB_PASSWORD = DB.password

# ============================================================
# CONNECT TO SUPABASE
# ============================================================

print("🔄 Connecting to Supabase...")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )

    print("✅ Connected to Supabase successfully!")

except Exception as e:
    print("\n❌ Connection failed!")
    print("Error:", e)
    print("\nCheck your:")
    print("1. Database Host")
    print("2. Database Password")
    print("3. Port")
    print("4. Database name")
    exit()


# ============================================================
# GET ALL PUBLIC TABLES
# ============================================================

query = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;
"""

try:
    tables_df = pd.read_sql(query, conn)

except Exception as e:
    print("❌ Could not get tables:", e)
    conn.close()
    exit()


tables = tables_df["table_name"].tolist()

print("\n========================================")
print(f"📊 TOTAL TABLES FOUND: {len(tables)}")
print("========================================")

for i, table in enumerate(tables, start=1):
    print(f"{i}. {table}")


# ============================================================
# CREATE EXPORT FOLDER
# ============================================================

output_folder = "supabase_export"

os.makedirs(output_folder, exist_ok=True)

print("\n📁 Export folder:", os.path.abspath(output_folder))


# ============================================================
# EXPORT EVERY TABLE
# ============================================================

print("\n========================================")
print("🚀 STARTING EXPORT")
print("========================================\n")

success = 0
failed = 0

for index, table_name in enumerate(tables, start=1):

    print(f"[{index}/{len(tables)}] 📥 Exporting: {table_name}")

    try:

        # Safely quote table name
        safe_table_name = '"' + table_name.replace('"', '""') + '"'

        # Read table
        df = pd.read_sql(
            f"SELECT * FROM {safe_table_name}",
            conn
        )

        # Make safe filename
        safe_filename = re.sub(
            r'[<>:"/\\|?*]',
            '_',
            table_name
        )

        filepath = os.path.join(
            output_folder,
            safe_filename + ".csv"
        )

        # Save CSV
        df.to_csv(
            filepath,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            f"    ✅ {len(df):,} rows exported"
        )

        success += 1

    except Exception as e:

        print(
            f"    ❌ Failed: {e}"
        )

        failed += 1


# ============================================================
# CLOSE CONNECTION
# ============================================================

conn.close()


# ============================================================
# FINAL RESULT
# ============================================================

print("\n")
print("========================================")
print("🎉 EXPORT FINISHED")
print("========================================")

print(f"✅ Successfully exported : {success}")
print(f"❌ Failed                : {failed}")
print(f"📊 Total tables          : {len(tables)}")

print("\n📁 CSV files location:")
print(os.path.abspath(output_folder))

print("\nDone! 🚀")