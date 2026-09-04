import psycopg2
import pandas as pd
import os
import re
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from db_env import db_config  # noqa: E402


# ============================================================
# CONFIGURATION
# ============================================================

DB = db_config()

DB_HOST = DB.host
DB_PORT = DB.port
DB_NAME = DB.name
DB_USER = DB.user
DB_PASSWORD = DB.password

# Export locations
BASE_DIR = Path(__file__).resolve().parent

OUTPUT_FOLDER = BASE_DIR / "supabase_export"
ZIP_FILE = BASE_DIR / "supabase_all_tables.zip"


# ============================================================
# CONNECT TO SUPABASE / POSTGRESQL
# ============================================================

print("\n🔄 Connecting to Supabase...")

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

    sys.exit(1)


# ============================================================
# GET ALL PUBLIC TABLES
# ============================================================

print("\n🔍 Fetching all public tables...")

query = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;
"""

try:
    tables_df = pd.read_sql_query(query, conn)

except Exception as e:
    print("❌ Could not get tables:", e)
    conn.close()
    sys.exit(1)


tables = tables_df["table_name"].tolist()


# ============================================================
# TABLE SUMMARY
# ============================================================

print("\n========================================")
print(f"📊 TOTAL PUBLIC TABLES FOUND: {len(tables)}")
print("========================================")

for i, table in enumerate(tables, start=1):
    print(f"{i:>2}. {table}")


# ============================================================
# PREPARE EXPORT FOLDER
# ============================================================

print("\n========================================")
print("📁 PREPARING EXPORT FOLDER")
print("========================================")

# Remove previous export folder so old CSVs
# don't accidentally remain in the new ZIP.
if OUTPUT_FOLDER.exists():
    print("🧹 Removing previous export folder...")
    shutil.rmtree(OUTPUT_FOLDER)

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

print(f"📁 Export folder: {OUTPUT_FOLDER}")


# ============================================================
# REMOVE PREVIOUS ZIP
# ============================================================

if ZIP_FILE.exists():
    print("🧹 Removing previous ZIP...")
    ZIP_FILE.unlink()


# ============================================================
# EXPORT EVERY TABLE
# ============================================================

print("\n========================================")
print("🚀 STARTING CSV EXPORT")
print("========================================\n")

success = 0
failed = 0
total_rows = 0

exported_files = []
failed_tables = []


for index, table_name in enumerate(tables, start=1):

    print(
        f"[{index}/{len(tables)}] 📥 Exporting: {table_name}"
    )

    try:

        # ----------------------------------------------------
        # Safely quote PostgreSQL table name
        # ----------------------------------------------------

        safe_table_name = '"' + table_name.replace('"', '""') + '"'

        # ----------------------------------------------------
        # Read complete table
        # ----------------------------------------------------

        df = pd.read_sql_query(
            f"SELECT * FROM {safe_table_name}",
            conn
        )

        # ----------------------------------------------------
        # Make filesystem-safe filename
        # ----------------------------------------------------

        safe_filename = re.sub(
            r'[<>:"/\\|?*]',
            '_',
            table_name
        )

        filepath = OUTPUT_FOLDER / f"{safe_filename}.csv"

        # ----------------------------------------------------
        # Save CSV
        # ----------------------------------------------------

        df.to_csv(
            filepath,
            index=False,
            encoding="utf-8-sig"
        )

        row_count = len(df)

        total_rows += row_count
        success += 1

        exported_files.append(filepath)

        print(
            f"    ✅ {row_count:,} rows"
            f" | {len(df.columns):,} columns"
            f" | {filepath.name}"
        )

    except Exception as e:

        failed += 1

        failed_tables.append(
            {
                "table": table_name,
                "error": str(e)
            }
        )

        print(
            f"    ❌ Failed: {e}"
        )


# ============================================================
# CLOSE DATABASE CONNECTION
# ============================================================

conn.close()

print("\n🔒 Database connection closed.")


# ============================================================
# CREATE ZIP FILE
# ============================================================

print("\n========================================")
print("📦 CREATING ZIP FILE")
print("========================================")

try:

    # shutil.make_archive automatically creates .zip
    # from the complete export folder.
    archive_without_extension = ZIP_FILE.with_suffix("")

    created_archive = shutil.make_archive(
        base_name=str(archive_without_extension),
        format="zip",
        root_dir=str(OUTPUT_FOLDER)
    )

    print("✅ ZIP created successfully!")
    print(f"📦 {created_archive}")

except Exception as e:

    print("❌ ZIP creation failed!")
    print("Error:", e)

    sys.exit(1)


# ============================================================
# VERIFY ZIP
# ============================================================

print("\n========================================")
print("🔎 VERIFYING ZIP")
print("========================================")

try:

    import zipfile

    with zipfile.ZipFile(ZIP_FILE, "r") as zip_ref:

        zip_files = [
            name
            for name in zip_ref.namelist()
            if name.lower().endswith(".csv")
        ]

        bad_files = zip_ref.testzip()

    if bad_files is None:
        print("✅ ZIP integrity check passed!")

    else:
        print(
            f"❌ ZIP contains a corrupted file: {bad_files}"
        )

    print(
        f"📄 CSV files inside ZIP: {len(zip_files)}"
    )

except Exception as e:

    print("❌ ZIP verification failed!")
    print("Error:", e)


# ============================================================
# FINAL RESULT
# ============================================================

print("\n")
print("========================================")
print("🎉 SUPABASE EXPORT FINISHED")
print("========================================")

print(f"📊 Total tables found       : {len(tables)}")
print(f"✅ Successfully exported    : {success}")
print(f"❌ Failed                   : {failed}")
print(f"📈 Total rows exported      : {total_rows:,}")
print(f"📄 CSV files created        : {len(exported_files)}")

print("\n📁 CSV folder:")
print(OUTPUT_FOLDER)

print("\n📦 FINAL ZIP:")
print(ZIP_FILE)


# ============================================================
# FAILED TABLE REPORT
# ============================================================

if failed_tables:

    print("\n========================================")
    print("⚠️ FAILED TABLES")
    print("========================================")

    for item in failed_tables:
        print(f"\n❌ {item['table']}")
        print(f"   Error: {item['error']}")

else:

    print("\n========================================")
    print("✅ ALL TABLES EXPORTED SUCCESSFULLY")
    print("========================================")


print("\n🚀 Done!")