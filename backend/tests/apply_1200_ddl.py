"""PHASE 2 — EXECUTE the CSE 6A 1,200 migration DDL against live Supabase.

Reads plan_1200_6a/1200_cohort_migration_proposed.sql, re-asserts the
additive/non-destructive audit (belt-and-suspenders, never blind-trusts the
file), then executes every top-level statement inside ONE transaction via
asyncpg. Any error => full rollback, exit code 3, nothing persisted.

Post-DDL (after commit, read-only):
  * the 6 new tables (+ career_preferences_v2) exist
  * every ADD COLUMN targeted by the DDL now exists
  * every planned index exists
  * helper functions app_role/app_user_id/app_student_id/app_faculty_id exist
  * RLS enabled flags match the migration intent
  * placement policies (2) exist
  * performance trigger still present and identical to migration 18
  * pre-flight fingerprint tables are byte-identical (count + md5 hash)
  * all new tables contain 0 rows (no data was loaded)

Produces plan_1200_6a/phase2_ddl_apply_live.json.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
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
DDL_FILE = REPO_ROOT / "plan_1200_6a" / "1200_cohort_migration_proposed.sql"
PREFLIGHT_REPORT = REPO_ROOT / "plan_1200_6a" / "preflight_1200_live.json"
MIG18 = REPO_ROOT / "migrations" / "18_marks_remarks_derivation.sql"

# reuse helpers from the pre-flight module (read-only logic only)
_pre = importlib.util.spec_from_file_location(
    "preflight_1200_apply", CWD.parents[1] / "tests" / "preflight_1200_apply.py"
).loader.load_module()

NEW_TABLES = _pre.NEW_TABLES
FINGERPRINT_TABLES = _pre.FINGERPRINT_TABLES
RLS_ENABLE_TABLES = NEW_TABLES + ["career_preferences"]
PLANNED_INDEXES = [
    "uq_attendance_weekly_grain", "idx_att_weekly_student_subj_week",
    "uq_learning_activity_grain", "idx_learning_activity_student_subj_week",
    "idx_skill_profile_student_sem", "idx_skill_profile_domain",
    "idx_placement_status",
    "uq_student_lifestyle_grain",
    "uq_career_pref_v2_student", "idx_career_pref_v2_domain",
    "idx_students_department", "idx_students_admission_year",
    "idx_enrollment_student", "idx_enrollment_subject", "idx_enrollment_faculty",
    "idx_enrollment_academic_year",
    "idx_performance_student", "idx_performance_subject_sem",
    "idx_sem_summary_student", "idx_sem_summary_academic_year",
]
EXPECTED_ALTER_ADD = [
    ("students", "division"), ("students", "cohort_id"), ("students", "source_dataset"),
    ("students", "generation_version"), ("students", "dataset_version"),
    ("student_subject_enrollment", "division"), ("student_subject_enrollment", "subject_domain"),
    ("student_subject_enrollment", "subject_skill"),
    ("student_subject_performance", "division"), ("student_subject_performance", "assignment_score"),
    ("student_subject_performance", "quiz_avg_marks"),
    ("student_subject_performance", "submission_delay_days"),
    ("student_subject_performance", "pre_endsem_assessment_pct"),
    ("student_subject_performance", "subject_domain"),
    ("student_subject_performance", "subject_skill"),
    ("student_semester_summary", "division"),
    ("student_semester_summary", "previous_sem_sgpa"),
    ("student_semester_summary", "sgpa_drift"),
    ("student_semester_summary", "sgpa_rolling_mean_3"),
    ("student_semester_summary", "previous_sem_backlog_count"),
    ("student_semester_summary", "backlog_change"),
    ("student_semester_summary", "cumulative_backlog_events"),
    ("student_semester_summary", "backlog_trajectory"),
    ("student_semester_summary", "attendance_aggregate_pct"),
    ("student_semester_summary", "is_m1_deployment_boundary"),
    ("student_semester_summary", "target_available_if_completed"),
    ("faculty_student_map", "mapping_id"), ("faculty_student_map", "semester_no"),
    ("faculty_student_map", "mapping_type"), ("faculty_student_map", "is_active"),
]


def split_top_level_statements(sql: str) -> List[str]:
    """Split on top-level ';', respecting line comments, '', "", and $tag$ bodies."""
    stmts: List[str] = []
    buf: List[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch, nxt = sql[i], sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            while i < n and sql[i] != "\n":
                buf.append(sql[i]); i += 1
            continue
        if ch == "'":
            buf.append(ch); i += 1
            while i < n:
                c = sql[i]
                buf.append(c)
                if c == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        buf.append(sql[i + 1]); i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == '"':
            buf.append(ch); i += 1
            while i < n:
                c = sql[i]
                buf.append(c)
                if c == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        buf.append(sql[i + 1]); i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "$":
            m = re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                end = sql.find(tag, i + len(tag))
                if end == -1:
                    raise ValueError("unterminated dollar-quote: " + tag)
                buf.append(sql[i : end + len(tag)])
                i = end + len(tag)
                continue
        if ch == ";":
            buf.append(ch)
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def strip_transaction_wrappers(stmts: List[str]) -> List[str]:
    out = []
    for s in stmts:
        s2 = re.sub(r"(?mi)^\s*(BEGIN|COMMIT)\s*;\s*$", "", s)
        if not re.sub(r"(?ms)--[^\n]*\n?", "", s2).strip():
            continue  # comment-only chunk
        s2 = s2.strip()
        if s2:
            out.append(s2)
    return out


def additivity_audit(ddl_text: str) -> Dict[str, Any]:
    comment_free = re.sub(r"--[^\n]*", "", ddl_text)
    forbidden = {
        "DROP": bool(re.search(r"\bDROP\b", comment_free, re.I)),
        "DELETE": bool(re.search(r"\bDELETE\b", comment_free, re.I)),
        "TRUNCATE": bool(re.search(r"\bTRUNCATE\b", comment_free, re.I)),
        "UPDATE": bool(re.search(r"\bUPDATE\b", comment_free, re.I)),
        "ALTER_DROP": bool(re.search(r"ALTER\s+TABLE[^;]*\bDROP\b", comment_free, re.I)),
        "ALTER_COLUMN_TYPE": bool(re.search(r"ALTER\s+COLUMN\s+\w+\s+TYPE\b", comment_free, re.I)),
        "INSERT_VALUES": bool(re.search(r"\bINSERT\s+INTO\b", comment_free, re.I)),
    }
    return {
        "guard_stu6a_present": "STU6A%" in ddl_text,
        "forbidden": forbidden,
        "clean": "STU6A%" in ddl_text and all(not v for v in forbidden.values()),
    }


async def _row_count(conn, table):
    return await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"')


async def _table_hash(conn, table):
    row = await conn.fetchrow(
        f'SELECT md5(string_agg(rh, \'\' ORDER BY rh)) AS th FROM '
        f'(SELECT md5(ROW(d.*)::text) AS rh FROM "{table}" d) sub'
    )
    return row["th"] if row and row["th"] else None


async def _connect_retry(cfg) -> asyncpg.Connection:
    """Retry connect with backoff; the Supabase pooler host occasionally fails DNS."""
    last: Any = None
    for attempt in range(6):
        try:
            return await asyncpg.connect(
                host=cfg.host, port=cfg.port, database=cfg.name, user=cfg.user,
                password=cfg.password, ssl="require", statement_cache_size=0, timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < 5:
                await asyncio.sleep(2 * (attempt + 1))
    raise last


async def apply_ddl(out_path: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {"phase": "PHASE_2_DDL_APPLY", "label": "cse6a_1200_ddl_apply_live"}

    pre = json.loads(PREFLIGHT_REPORT.read_text(encoding="utf-8"))
    if not pre.get("overall_gate"):
        report["error"] = "Phase-1 pre-flight did not pass; refusing to execute DDL."
        return report

    ddl_text = DDL_FILE.read_text(encoding="utf-8")
    audit = additivity_audit(ddl_text)
    report["audit_before_execute"] = audit
    if not audit["clean"]:
        report["error"] = "DDL additivity audit failed; refusing to execute."
        return report

    stmts = strip_transaction_wrappers(split_top_level_statements(ddl_text))
    report["statement_count"] = len(stmts)
    report["statements"] = [s.splitlines()[0][:80] for s in stmts]

    cfg = db_config()
    conn = await _connect_retry(cfg)

    executed: List[Dict[str, Any]] = []
    try:
        async with conn.transaction():
            for k, stmt in enumerate(stmts, 1):
                await conn.execute(stmt)
                executed.append(
                    {"n": k, "ok": True, "first_line": stmt.splitlines()[0][:100]}
                )
        report["ddl_executed"] = True
        report["executed_statements"] = executed
        report["commit"] = "committed"
    except Exception as exc:  # asyncpg transaction rolls back automatically
        report["ddl_executed"] = False
        report["commit"] = "rolled_back"
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["executed_statements"] = executed
        await conn.close()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        return report

    # ---------------- post-DDL verification (read-only) ---------------------
    ver: Dict[str, Any] = {}

    existing = {
        r["tablename"]
        for r in await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    }
    ver["new_tables_exist"] = {t: (t in existing) for t in NEW_TABLES}
    ver["new_tables_all_exist"] = all(t in existing for t in NEW_TABLES)

    rls_rows = await conn.fetch(
        "SELECT tablename, rowsecurity FROM pg_tables "
        "WHERE schemaname='public' AND tablename = ANY($1::text[])",
        RLS_ENABLE_TABLES,
    )
    rls_map = {r["tablename"]: r["rowsecurity"] for r in rls_rows}
    ver["rls_enabled"] = {t: bool(rls_map.get(t)) for t in RLS_ENABLE_TABLES}
    ver["rls_all_enabled"] = all(bool(rls_map.get(t)) for t in RLS_ENABLE_TABLES)

    pol = await conn.fetchval(
        "SELECT count(*) FROM pg_policies p WHERE p.schemaname='public' AND p.tablename='placement'"
    )
    ver["placement_policies_count"] = pol
    ver["placement_policies_expected"] = 2

    helpers = await conn.fetchval(
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.proname = ANY($1::text[])",
        ["app_role", "app_user_id", "app_student_id", "app_faculty_id"],
    )
    ver["helper_functions_count"] = helpers
    ver["helper_functions_expected"] = 4

    idx_rows = await conn.fetch(
        "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public'"
    )
    idx_names = {r["indexname"] for r in idx_rows}
    missing_idx = [i for i in PLANNED_INDEXES if i not in idx_names]
    ver["missing_indexes"] = missing_idx
    ver["indexes_all_exist"] = not missing_idx

    col_rows = await conn.fetch(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public'"
    )
    have_cols = {(r["table_name"], r["column_name"]) for r in col_rows}
    missing_cols = [(t, c) for t, c in EXPECTED_ALTER_ADD if (t, c) not in have_cols]
    ver["missing_added_columns"] = missing_cols
    ver["added_columns_all_exist"] = not missing_cols

    trig = await conn.fetchval(
        "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname='trigger_update_performance'"
    )
    trig_fn = await conn.fetchval(
        "SELECT pg_get_functiondef(p.oid) FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.proname='trg_calculate_performance'"
    )
    ver["trigger_exists"] = trig == 1
    mig18_body = _pre.extract_function_body(
        re.sub(r"--[^\n]*", "", MIG18.read_text(encoding="utf-8"))
    ) if MIG18.exists() else ""
    trig_body = _pre.extract_function_body(re.sub(r"--[^\n]*", "", trig_fn or ""))
    ver["trigger_matches_migration18"] = trig_body == mig18_body

    new_rows = {}
    for t in NEW_TABLES:
        new_rows[t] = await _row_count(conn, t)
    ver["new_table_row_counts"] = new_rows
    ver["new_tables_empty"] = all(v == 0 for v in new_rows.values())

    # projection: pre-DDL column set per touched table (from the phase-1 report)
    pre_cols = {}
    for t in pre.get("constraint_summary", {}):
        cols = [c["column_name"] for c in pre["constraint_summary"][t]["columns"]]
        if cols:
            pre_cols[t] = cols
    pre_fp = pre.get("pre_ddl_fingerprint", {})

    async def _projected_hash(table: str, cols: List[str]) -> str:
        colsql = ", ".join(f'"{c2}"' for c2 in cols)
        row = await conn.fetchrow(
            f"SELECT md5(string_agg(rh, '' ORDER BY rh)) AS th FROM "
            f"(SELECT md5(ROW({colsql})::text) AS rh FROM \"{table}\" d) sub"
        )
        return row["th"] if row and row["th"] else None

    fp_now, fp_ok = {}, True
    for t in FINGERPRINT_TABLES:
        if t not in existing:
            fp_now[t] = None
            continue
        cols = pre_cols.get(t)
        if cols:
            # projection-to-pre-DDL-columns proves existing values untouched
            fp_now[t] = {
                "count": await _row_count(conn, t),
                "hash_projected_to_pre_ddl_columns": await _projected_hash(t, cols),
            }
        else:
            # untouched table: full-row hash must match exactly
            fp_now[t] = {
                "count": await _row_count(conn, t),
                "hash": await _table_hash(conn, t),
            }
    unch = {}
    for t in FINGERPRINT_TABLES:
        a, b = pre_fp.get(t), fp_now.get(t)
        if a is None or b is None:
            unch[t] = bool(a is None and b is None)
            continue
        if pre_cols.get(t):
            # compare count plus projected hash; also record whether the plain
            # full-row (incl. new columns) hash moved (expected for ADD COLUMN)
            full_now = await _table_hash(conn, t)
            unch[t] = a["count"] == b["count"] and a["hash"] == b["hash_projected_to_pre_ddl_columns"]
            ver.setdefault("new_columns_added_baseline", {})[t] = {
                "count_same": a["count"] == b["count"],
                "pre_ddl_hash_over_old_shape": a["hash"],
                "post_ddl_hash_projected": b["hash_projected_to_pre_ddl_columns"],
                "post_ddl_hash_full_row_with_new_cols": full_now,
                "projected_identical": a["hash"] == b["hash_projected_to_pre_ddl_columns"],
            }
        else:
            unch[t] = a["count"] == b["count"] and a["hash"] == b["hash"]
        fp_ok = fp_ok and bool(unch[t])
    ver["fingerprint_unchanged"] = unch
    ver["fingerprint_all_unchanged"] = fp_ok
    ver["post_ddl_fingerprint"] = fp_now

    ver["pass"] = (
        ver["new_tables_all_exist"]
        and ver["rls_all_enabled"]
        and pol == 2
        and helpers == 4
        and not missing_idx
        and not missing_cols
        and trig == 1
        and trig_body == mig18_body
        and all(v == 0 for v in new_rows.values())
        and fp_ok
    )
    report["post_ddl_verification"] = ver

    await conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "plan_1200_6a" / "phase2_ddl_apply_live.json",
    )
    args = parser.parse_args()

    report = asyncio_run(apply_ddl(args.out))

    print("\n" + "=" * 76)
    print("  PHASE 2 — DDL APPLY   |   committed: "
          f"{report.get('commit')} | executed: {report.get('ddl_executed')}")
    print("=" * 76)
    if "error" in report:
        print("  ERROR:", report["error"])
        print("=" * 76)
        return 3
    ver = report["post_ddl_verification"]
    print(f"  new tables exist: {ver['new_tables_all_exist']}")
    print(f"  added columns exist: {ver['added_columns_all_exist']} "
          f"(missing={ver['missing_added_columns']})")
    print(f"  indexes exist: {ver['indexes_all_exist']} (missing={ver['missing_indexes']})")
    print(f"  helpers: {ver['helper_functions_count']}/4, "
          f"placement policies: {ver['placement_policies_count']}/2")
    print(f"  RLS enabled: {ver['rls_all_enabled']}")
    print(f"  trigger intact + matches mig18: {ver['trigger_matches_migration18']}")
    print(f"  new tables empty: {ver['new_tables_empty']}")
    print(f"  80-cohort fingerprint unchanged: {ver['fingerprint_all_unchanged']}")
    print(f"  POST-DDL VERIFICATION: {'PASS' if ver['pass'] else 'FAIL'}")
    print(f"\n  report written: {args.out}")
    print("=" * 76)
    return 0 if (report.get("ddl_executed") and ver["pass"]) else 3


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    raise SystemExit(main())