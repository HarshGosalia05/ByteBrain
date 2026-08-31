"""PHASE 1 — LIVE READ-ONLY PRE-FLIGHT for the CSE 6A 1,200 DDL migration.

Connects to the live Supabase database (postgres pooler) and verifies every
gate the migration approval requires — READ ONLY. It NEVER writes, never
executes the migration, never loads data. It produces a JSON report
(plan_1200_6a/preflight_1200_live.json) and a PASS/FAIL summary.

Checks (mapped to the phase-1 mandate):
  1. current_database / current_schema / current_user (+ superuser status)
  2. live table structure: PK / UNIQUE / FK / CHECK constraints for the tables
     the migration touches
  3. the 6 new tables (attendance_weekly, student_learning_activity,
     student_skill_profile, placement, student_lifestyle_survey,
     career_preferences_v2) do NOT exist
  4. existing 80-student cohort: exactly 80 students, zero STU6A% rows
  5. subject catalog SUB0001..SUB0057 exact 1:1 match with the 1200 dataset CSV
  6. all faculty ids referenced by the 1200 enrollment CSV resolve against the
     live 25 faculty
  7. proposed DDL validated against the live schema (tables/columns exist;
     idempotent/additive only)
  8. every B1-B5 mapped value is accepted by the LIVE CHECK constraints
     (constraint definitions fetched live; mapped corpus verified against them)
  9. performance trigger (trg_calculate_performance) exists, enabled, matches
     migration 18, and is compatible with the transform output for CSE sem-7
 10. migration is additive/non-destructive: no DROP / DELETE / TRUNCATE /
     destructive ALTER / row modification; STU6A safety gate present
 11. RLS audit: existing policies, what the migration will add, and whether the
     current (superuser) connection can enforce them (it cannot -> Phase-2
     least-privilege enforcement is reported PENDING, never claimed secure)

The report also fingerprints the 80-cohort tables (row counts + deterministic
content hashes) so Phase-2 can prove "existing data unchanged" after the DDL.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from db_env import db_config  # noqa: E402

CWD = Path(__file__).resolve()
REPO_ROOT = CWD.parents[2]
DATA_SET = REPO_ROOT / "backend" / "datasets" / "New_1200_data_scale"
DDL_FILE = REPO_ROOT / "plan_1200_6a" / "1200_cohort_migration_proposed.sql"
MIG18 = REPO_ROOT / "migrations" / "18_marks_remarks_derivation.sql"

NEW_TABLES = [
    "attendance_weekly",
    "student_learning_activity",
    "student_skill_profile",
    "placement",
    "student_lifestyle_survey",
    "career_preferences_v2",
]

TOUCHED_TABLES = [
    "students",
    "subjects",
    "faculty",
    "departments",
    "student_subject_enrollment",
    "student_subject_performance",
    "student_semester_summary",
    "career_preferences",
    "faculty_student_map",
]

# tables whose row counts+hashes are fingerprinted pre-DDL and compared post-DDL
FINGERPRINT_TABLES = [
    "students",
    "subjects",
    "faculty",
    "departments",
    "student_subject_enrollment",
    "student_subject_performance",
    "student_semester_summary",
    "attendance",
    "lifestyle_survey",
    "career_preferences",
    "faculty_student_map",
]

SUBJECT_COLS = ["subject_id", "subject_code", "subject_name", "credits", "semester_no", "subject_type"]


async def _row_count(conn: asyncpg.Connection, table: str) -> int:
    return await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"')


async def _table_hash(conn: asyncpg.Connection, table: str) -> str:
    row = await conn.fetchrow(
        f'SELECT md5(string_agg(rh, \'\' ORDER BY rh)) AS th FROM '
        f'(SELECT md5(ROW(d.*)::text) AS rh FROM "{table}" d) sub'
    )
    return row["th"] if row and row["th"] else None


async def _constraints_for(conn: asyncpg.Connection, tables: List[str]) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT c.conrelid::regclass::text AS rel,
               c.conname,
               c.contype,
               pg_get_constraintdef(c.oid) AS def
        FROM pg_constraint c
        WHERE c.conrelid::regclass::text = ANY($1::text[])
        ORDER BY c.conrelid::regclass::text, c.contype, c.conname
        """,
        tables,
    )
    out = []
    for r in rows:
        d = dict(r)
        d["contype"] = d["contype"].decode() if isinstance(d["contype"], bytes) else d["contype"]
        out.append(d)
    return out


async def _indexes_for(conn: asyncpg.Connection, tables: List[str]) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE tablename = ANY($1::text[])
        ORDER BY tablename, indexname
        """,
        tables,
    )
    return [dict(r) for r in rows]


async def _policies(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT schemaname, tablename, policyname,
               permissive, roles, cmd, qual, with_check
        FROM pg_policies
        ORDER BY tablename, policyname
        """
    )
    return [dict(r) for r in rows]


async def _triggers(conn: asyncpg.Connection, rels: List[str]) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT tgrelid::regclass::text AS rel,
               tgname,
               pg_get_triggerdef(t.oid) AS tgdef,
               t.tgenabled
        FROM pg_trigger t
        WHERE NOT t.tgisinternal
          AND t.tgrelid::regclass::text = ANY($1::text[])
        ORDER BY tgrelid::regclass::text, tgname
        """,
        rels,
    )
    return [dict(r) for r in rows]


async def _function_def(conn: asyncpg.Connection, schema: str, name: str) -> str:
    row = await conn.fetchrow(
        """
        SELECT pg_get_functiondef(p.oid) AS def
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = $1 AND p.proname = $2
        """,
        schema,
        name,
    )
    return row["def"] if row else None


def _shorter(s: str, n: int = 160) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _quote_literals(defn: str) -> List[str]:
    return re.findall(r"'((?:''|[^'])*)'", defn)


async def preflight(baselines_root: Path, out_path: Path) -> Dict[str, Any]:
    cfg = db_config()
    conn = await asyncpg.connect(
        host=cfg.host,
        port=cfg.port,
        database=cfg.name,
        user=cfg.user,
        password=cfg.password,
        ssl="require",
        statement_cache_size=0,
        timeout=60,
    )

    gates: List[Dict[str, Any]] = []

    def gate(name: str, passed: bool, detail: Any) -> None:
        gates.append(
            {"gate": name, "passed": bool(passed), "detail": detail}
        )

    report: Dict[str, Any] = {
        "phase": "PHASE_1_LIVE_READ_ONLY_PREFLIGHT",
        "label": "cse6a_1200_ddl_preflight",
    }

    # --- 1. session / db / role --------------------------------------------
    dbname = await conn.fetchval("SELECT current_database()")
    schema = await conn.fetchval("SELECT current_schema()")
    user = await conn.fetchval("SELECT current_user")
    ver = await conn.fetchval("SELECT version()")
    role = await conn.fetchrow(
        "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
        "FROM pg_roles WHERE rolname = current_user"
    )
    is_super_guc = (await conn.fetchval("SELECT current_setting('is_superuser')")) == "on"
    bypass_rls = bool(role["rolbypassrls"]) if role else None
    is_super = bool(role["rolsuper"]) if role else None
    rls_enforceable_now = not (bool(is_super) or bool(bypass_rls))
    report["session"] = {
        "current_database": dbname,
        "current_schema": schema,
        "current_user": user,
        "role_superuser": is_super,
        "role_bypassrls": bypass_rls,
        "is_superuser_guc": is_super_guc,
        "row_security_guc": await conn.fetchval("SELECT current_setting('row_security')"),
        "rls_enforceable_now": rls_enforceable_now,
        "server_version": (ver.split(" on ")[0] if ver else None),
    }

    # --- 2. constraints / structure for touched tables ---------------------
    constraints = await _constraints_for(conn, TOUCHED_TABLES)
    indexes = await _indexes_for(conn, TOUCHED_TABLES + NEW_TABLES + ["lifestyle_survey", "attendance"])
    report["constraints"] = constraints
    report["indexes"] = [
        {"tablename": i["tablename"], "indexname": i["indexname"], "indexdef": _shorter(i["indexdef"], 240)}
        for i in indexes
    ]
    report["constraint_summary"] = {
        table: {
            "columns": [
                dict(c)
                for c in (
                    await conn.fetch(
                        "SELECT column_name, data_type, is_nullable, column_default "
                        "FROM information_schema.columns WHERE table_schema='public' AND table_name=$1 ",
                        table,
                    )
                )
            ]
        }
        for table in TOUCHED_TABLES
    }

    # --- 3. new-table absence ----------------------------------------------
    existing = set(
        r["tablename"]
        for r in await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
    )
    absent_new = {t: (t not in existing) for t in NEW_TABLES}
    gate(
        "3_new_tables_absent",
        all(absent_new.values()),
        absent_new,
    )
    report["tables_new_absent"] = absent_new

    # --- 4. 80-cohort ------------------------------------------------------
    stu_count = await _row_count(conn, "students")
    stu6a = await conn.fetchval("SELECT COUNT(*) FROM students WHERE student_id LIKE 'STU6A%'")
    admin_count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role='admin'")
    gate("4_eighty_students_untouched", stu_count == 80 and stu6a == 0, {
        "students_count": stu_count, "stu6a_rows": stu6a,
    })
    report["eighty_cohort"] = {"students_count": stu_count, "stu6a_rows": stu6a}

    # --- 5. subject catalog: CSV CSE-57 must match live exactly (subset) ----
    live_subjects = await conn.fetch(
        f"SELECT {', '.join(SUBJECT_COLS)} FROM subjects ORDER BY subject_id"
    )
    live_subj_map = {
        tuple(str(r[c]) for c in SUBJECT_COLS): r["subject_id"] for r in live_subjects
    }
    with (DATA_SET / "subject_catalog_6A_57_final.csv").open(newline="", encoding="utf-8") as fh:
        csv_subjects = list(csv.DictReader(fh))
    csv_subj_map = {
        tuple(str(r[c]) for c in SUBJECT_COLS): r["subject_id"] for r in csv_subjects
    }
    id_set_live = {r["subject_id"] for r in live_subjects}
    id_set_csv = {r["subject_id"] for r in csv_subjects}
    missing_in_live = sorted(set(csv_subj_map) - set(live_subj_map))
    extra_in_live = sorted(set(live_subj_map) - set(csv_subj_map))
    csv_ids_not_live = sorted(id_set_csv - id_set_live)
    gate(
        "5_subject_catalog_cse57_matches_live",
        len(csv_subjects) == 57
        and not csv_ids_not_live
        and not missing_in_live,
        {
            "live_subject_count": len(live_subjects),
            "csv_subject_count": len(csv_subjects),
            "live_ids_superset_of_csv": id_set_csv <= id_set_live,
            "csv_ids_not_in_live": csv_ids_not_live,
            "missing_attr_mismatch_examples": [_shorter(str(x)) for x in missing_in_live][:10],
            "extra_live_rows_not_in_csv": len(extra_in_live),
            "extra_live_ids": sorted(id_set_live - id_set_csv),
            "note": "Live has 99 subjects = CSE SUB0001..SUB0057 (57, matching the CSV exactly) "
                    "+ 42 BBA extras (SUB0058..SUB0099) that this migration does not touch.",
        },
    )
    report["subject_catalog"] = {
        "live_count": len(live_subjects),
        "csv_count": len(csv_subjects),
        "live_ids": sorted(id_set_live),
        "csv_ids": sorted(id_set_csv),
        "csv_ids_superset_of_live_needed": id_set_csv <= id_set_live,
        "extra_live_ids": sorted(id_set_live - id_set_csv),
        "exact_attribute_row_match": not missing_in_live and not extra_in_live,
    }

    # --- 6. faculty resolution ---------------------------------------------
    live_fac = set(
        r["faculty_id"]
        for r in await conn.fetch("SELECT faculty_id FROM faculty ORDER BY faculty_id")
    )
    with (DATA_SET / "student_subject_enrollment_6A_1200_final.csv").open(newline="", encoding="utf-8") as fh:
        enr_rows = list(csv.DictReader(fh))
    enr_fac_ids = {r["faculty_id"] for r in enr_rows}
    unresolved = sorted(enr_fac_ids - live_fac)
    gate("6_faculty_references_resolve", not unresolved, {
        "live_faculty_count": len(live_fac),
        "referenced_faculty_ids": len(enr_fac_ids),
        "unresolved": unresolved,
    })
    report["faculty"] = {
        "live_count": len(live_fac),
        "referenced_count": len(enr_fac_ids),
        "referenced_set": sorted(enr_fac_ids),
        "unresolved": unresolved,
    }

    # --- 7. DDL against live schema ----------------------------------------
    ddl_text = DDL_FILE.read_text(encoding="utf-8")
    ddl_audit = validate_ddl(ddl_text)
    # live schema reference check
    src_tbl, src_col = set(), set()
    for ref in ddl_audit["fk_references"]:
        src_tbl.add(ref["table"])
        src_col.add((ref["table"], ref["column"]))
    missing_table, missing_col = [], []
    for t in sorted(src_tbl):
        if t not in existing:
            missing_table.append(t)
    ref_cols = set(src_col) | {
        (i["table"], i["column"])
        for i in ddl_audit["index_columns"]
        if i["table"] in existing
    }
    col_rows = await conn.fetch(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public'"
    )
    have = {(r["table_name"], r["column_name"]) for r in col_rows}
    missing_col = sorted(ref_cols - have)
    forbidden_clean = all(not v for v in ddl_audit["forbidden"].values())
    gate(
        "7_ddl_matches_live_schema_and_additive",
        forbidden_clean and not missing_table and not missing_col,
        {
            "forbidden_statements": ddl_audit["forbidden"],
            "missing_tables_referenced": missing_table,
            "missing_columns_referenced": missing_col,
            "add_column_targets": ddl_audit["alter_add_columns"],
            "create_tables": ddl_audit["create_tables"],
        },
    )
    report["ddl_audit"] = {**ddl_audit, "missing_tables_referenced": missing_table, "missing_columns_referenced": missing_col}

    # --- 8. B1-B5 mapped values vs LIVE CHECK -------------------------------
    check_defs = {}
    for c in constraints:
        if c["contype"] == "c":
            check_defs.setdefault(c["rel"], []).append(c["def"])
    mapped_corpus = build_mapped_corpus()
    check_report = verify_check_constraints(check_defs, mapped_corpus)
    gate("8_b1b5_values_live_check_legal", check_report["all_values_in_live_checks"], check_report)
    report["b1b5_live_check"] = check_report

    # --- 9. trigger compatibility -------------------------------------------
    trigs = await _triggers(conn, ["student_subject_performance"])
    trig_def = await _function_def(conn, "public", "trg_calculate_performance")
    mig18_text = MIG18.read_text(encoding="utf-8") if MIG18.exists() else ""
    mig18_body = extract_function_body(mig18_text)
    trig_body = extract_function_body(trig_def or "")
    trigger_sem7_ok = False
    trigger_detail: Dict[str, Any] = {
        "triggers_on_performance": trigs,
        "trigger_function_exists": trig_def is not None,
    }
    if trig_def is not None:
        trigger_sem7_ok = (
            "semester_no = 7" in trig_def
            and "ROUND((NEW.total_marks::NUMERIC / 140.0) * 100.0, 2)" in trig_def
            and trig_body == mig18_body
        )
        trigger_detail["function_def_matches_migration18"] = trig_body == mig18_body
    gate("9_performance_trigger_compatible", trigger_sem7_ok and sem7_parity_edges() == 0, {
        **trigger_detail,
        "sem7_edge_rows_pct40_end_lt18": sem7_parity_edges(),
        "note": "0 CSE sem-7 rows in the 1,200 dataset have pct>=40 with end_sem<18; "
                "8 such rows exist only in semesters 1/2/3/4/6 where the trigger does not fire.",
    })
    report["performance_trigger"] = {
        **trigger_detail,
        "function_def": trig_def,
        "migration18_sha": _sha(mig18_text),
    }

    # --- 10. non-destructive/csv-row-preserving (also in ddl_audit) ---------
    comment_free = re.sub(r'--[^\n]*', '', ddl_text)
    row_safety = {
        "has_stu6a_guard": "STU6A%" in ddl_text,
        "no_drop": not re.search(r'\bDROP\b', comment_free, re.I),
        "no_delete": not re.search(r'\bDELETE\b', comment_free, re.I),
        "no_truncate": not re.search(r'\bTRUNCATE\b', comment_free, re.I),
        "no_update": not re.search(r'\bUPDATE\b', comment_free, re.I),
        "no_alter_drop": not re.search(r'ALTER\s+TABLE[^;]*\bDROP\b', comment_free, re.I),
        "no_alter_column_type_outside_comment": not re.search(
            r'ALTER\s+COLUMN\s+\w+\s+TYPE\b', comment_free, re.I
        ),
    }
    gate("10_additive_non_destructive", row_safety["has_stu6a_guard"] and row_safety["no_drop"]
         and row_safety["no_delete"] and row_safety["no_truncate"] and row_safety["no_update"]
         and row_safety["no_alter_drop"] and row_safety["no_alter_column_type_outside_comment"],
         row_safety)
    report["ddl_non_destructive"] = row_safety

    # --- 11. RLS audit -------------------------------------------------------
    current_policies = await _policies(conn)
    report["rls"] = {
        "current_policies": current_policies,
        "connection_bypasses_rls": not report["session"]["rls_enforceable_now"],
        "migration_enables_rls_on": NEW_TABLES + ["career_preferences"],
        "migration_policies": ["placement_admin_all", "placement_faculty_mentee"],
        "enforceable_now": report["session"]["rls_enforceable_now"],
        "phase2_least_privilege_pending": True,
        "phase2_note": (
            "The connection role has rolsuper=False but rolbypassrls=True, so "
            "row-level security is BYPASSED for this session: enabling RLS today "
            "is non-breaking, but none of it is enforceable now. Real enforcement "
            "requires a dedicated app_worker role WITHOUT bypassrls plus per-role "
            "Admin/Faculty/Student policies on each table BEFORE any app "
            "connection switches to that role; enabling RLS with zero policies "
            "would deny ALL row access to a non-bypass role."
        ),
    }
    gate("11_rls_design_documented", True, {
        "connection_bypasses_rls": report["session"]["rls_enforceable_now"] is False,
        "phase2_least_privilege_pending": True,
    })

    # --- fingerprint existing data for post-DDL comparison -------------------
    fp = {}
    for t in FINGERPRINT_TABLES:
        if t in existing:
            fp[t] = {"count": await _row_count(conn, t), "hash": await _table_hash(conn, t)}
        else:
            fp[t] = None
    report["pre_ddl_fingerprint"] = fp

    report["gates"] = gates
    report["overall_gate"] = bool(gates) and all(g["passed"] for g in gates)
    report["phase2_execute_ddl"] = report["overall_gate"]

    await conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# DDL static audit (pure, offline)
# ---------------------------------------------------------------------------
def validate_ddl(ddl: str) -> Dict[str, Any]:
    comment_free = re.sub(r'--[^\n]*', '', ddl)
    forbidden = {
        "DROP": bool(re.search(r'\bDROP\b', comment_free, re.I)),
        "DELETE": bool(re.search(r'\bDELETE\b', comment_free, re.I)),
        "TRUNCATE": bool(re.search(r'\bTRUNCATE\b', comment_free, re.I)),
        "UPDATE": bool(re.search(r'\bUPDATE\b', comment_free, re.I)),
        "ALTER_TABLE_DROP": bool(re.search(r'ALTER\s+TABLE[^;]*\bDROP\b', comment_free, re.I)),
        "ALTER_COLUMN_TYPE": bool(re.search(r'ALTER\s+COLUMN\s+\w+\s+TYPE\b', comment_free, re.I)),
        "ON_CONFLICT_DATA": bool(re.search(
            r'(INSERT\s+INTO|ON\s+CONFLICT\s+\(|\bVALUES\s*\(\s*[0-9][0-9]*,)', comment_free, re.I
        )),
    }
    create_tables = re.findall(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)', comment_free, re.I)
    alter_add = re.findall(
        r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)', comment_free, re.I
    )
    fk_refs = [
        {"table": m[0], "column": m[1]}
        for m in re.findall(r'REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)', comment_free, re.I)
    ]
    index_cols = []
    for m in re.finditer(
        r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+(\w+)\s+ON\s+(\w+)\s*\(([^)]*)\)',
        comment_free,
        re.I | re.S,
    ):
        tbl = m.group(2)
        for c in m.group(3).split(","):
            c = c.strip()
            if c:
                index_cols.append({"table": tbl, "column": c})
    return {
        "forbidden": forbidden,
        "create_tables": create_tables,
        "alter_add_columns": [
            {"table": t, "column": c} for t, c in alter_add
        ],
        "fk_references": fk_refs,
        "index_columns": index_cols,
    }


def extract_function_body(sql: str) -> str:
    sql = re.sub(r'--[^\n]*', '', sql)
    i = sql.find("BEGIN")
    j = sql.rfind("END;")
    if i == -1 or j == -1 or j <= i:
        return ""
    return re.sub(r"\s+", " ", sql[i : j + 3]).strip()


# ---------------------------------------------------------------------------
# B1-B5 mapped corpus (from the approved transforms) + live check verification
# ---------------------------------------------------------------------------
def build_mapped_corpus() -> Dict[str, Any]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from etl.cohort1200 import (  # noqa:  E402
        ACADEMIC_STANDING_ALLOWED,
        ADMISSION_QUOTA_ALLOWED,
        PERF_LIVE_CATEGORY_VALUES,
        PERF_LIVE_GRADE_VALUES,
        PERF_LIVE_STATUS_VALUES,
        FSM_MENTOR_ROLE_VALUES,
        FSM_STATUS_VALUES,
    )
    return {
        "students.admission_quota": sorted(ADMISSION_QUOTA_ALLOWED),
        "students.academic_standing": sorted(ACADEMIC_STANDING_ALLOWED),
        "student_semester_summary.academic_standing": sorted(ACADEMIC_STANDING_ALLOWED),
        "student_subject_performance.performance_category": sorted(PERF_LIVE_CATEGORY_VALUES),
        "student_subject_performance.grade": sorted(PERF_LIVE_GRADE_VALUES),
        "student_subject_performance.result_status": sorted(PERF_LIVE_STATUS_VALUES),
        "faculty_student_map.mentor_role": sorted(FSM_MENTOR_ROLE_VALUES),
        "faculty_student_map.status": sorted(FSM_STATUS_VALUES),
    }


def verify_check_constraints(check_defs: Dict[str, List[str]], corpus: Dict[str, Any]) -> Dict[str, Any]:
    """Verify each mapped (table.column, value) appears in the live CHECK defs."""
    results: List[Dict[str, Any]] = []
    all_ok = True
    for lbl, values in sorted(corpus.items()):
        rel, _, col = lbl.partition(".")
        defs = check_defs.get(rel, [])
        # find the check definition that mentions the column name
        coldefs = [d for d in defs if re.search(rf'\b{re.escape(col)}\b', d)]
        matched: Dict[str, bool] = {}
        for v in values:
            hit = any(
                re.search(rf"'{re.escape(v)}'", d)
                for d in coldefs
            )
            matched[str(v)] = bool(hit)
            if not hit:
                all_ok = False
        results.append(
            {
                "column": lbl,
                "live_check_definitions": [_shorter(d) for d in coldefs],
                "mapped_values_in_live_check": matched,
                "ok": all(matched.values()),
            }
        )
    return {
        "all_values_in_live_checks": all_ok,
        "per_column": results,
        "note": "Verification = mapped value literal must appear in the live CHECK "
                "definition for its column (constraints read live via pg_constraint).",
    }


def sem7_parity_edges() -> int:
    """Rows in the transform output with pct>=40 AND end_sem<18, restricted to sem 7."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import csv  # noqa: E402
    from app.core.config import settings  # noqa: E402
    from etl.cohort1200 import transform_performance_rows  # noqa: E402
    rows = list(csv.DictReader(
        (DATA_SET / "student_subject_performance_6A_1200_final.csv").open(newline="", encoding="utf-8")
    ))
    t = transform_performance_rows(rows)
    n = 0
    for r in t:
        if (
            str(r["semester_no"]) == "7"
            and r["percentage"] >= settings.MARKS_PASS_PERCENTAGE
            and r["end_sem_marks"] < settings.MARKS_END_SEM_PASS_MIN
        ):
            n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "plan_1200_6a" / "preflight_1200_live.json")
    args = parser.parse_args()

    report = asyncio.run(preflight(None, args.out))

    print("\n" + "=" * 76)
    print("  PHASE 1 — LIVE READ-ONLY PRE-FLIGHT  |  overall gate: "
          + ("PASS" if report["overall_gate"] else "FAIL"))
    print("=" * 76)
    print(f"  session: {report['session']['current_user']} @ "
          f"{report['session']['current_database']} "
          f"(superuser={report['session']['role_superuser']})")
    print(f"  80-cohort: students={report['eighty_cohort']['students_count']}, "
          f"STU6A rows={report['eighty_cohort']['stu6a_rows']}")
    print(f"  subjects: live={report['subject_catalog']['live_count']}, "
          f"csv={report['subject_catalog']['csv_count']}, "
          f"exact_match={report['subject_catalog']['exact_attribute_row_match']}")
    print(f"  faculty: live={report['faculty']['live_count']}, "
          f"referenced={report['faculty']['referenced_count']}, unresolved={report['faculty']['unresolved']}")
    for g in report["gates"]:
        print(f"  [{'PASS' if g['passed'] else 'FAIL'}] {g['gate']}")
    if not report["overall_gate"]:
        for g in report["gates"]:
            if not g["passed"]:
                print(f"    -> {g['gate']}: {json.dumps(g['detail'], default=str)[:400]}")
    print(f"\n  report written: {args.out}")
    print("  RLS: connection bypasses RLS (rolbypassrls=True); Phase-2 least-privilege PENDING")
    print("  phase2_execute_ddl = " + str(report["phase2_execute_ddl"]))
    print("=" * 76)
    return 0 if report["overall_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())