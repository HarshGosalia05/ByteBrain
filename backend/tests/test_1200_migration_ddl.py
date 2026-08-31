"""Schema/migration content tests for the proposed 1,200-cohort DDL.

Validates `plan_1200_6a/1200_cohort_migration_proposed.sql` (PROPOSED ONLY,
never executed) without touching a live database. Scope is the two schema gaps
resolved for the dry-run integration:
  * student_subject_enrollment gains `subject_domain`, `subject_skill`
    (generated M4 domain/skill intelligence fields at the enrollment grain),
    additive and nullable, existing PK/UNIQUE/FKs untouched.
  * faculty_student_map gains dedicated `mapping_id`, `semester_no`,
    `mapping_type`, `is_active` columns — the new CSV shape is preserved WITHOUT
    re-mapping onto the live mentor columns (mentor_role CHECK must stay legal,
    status stays 'Active'/'Inactive', semester_no never ab-orbed into anything).
"""

from __future__ import annotations

import unittest
from pathlib import Path

PLAN_DIR = Path(__file__).resolve().parents[2] / "plan_1200_6a"
DDL_FILE = PLAN_DIR / "1200_cohort_migration_proposed.sql"


class TestProposed1200DDL(unittest.TestCase):
    def setUp(self):
        self.sql = DDL_FILE.read_text(encoding="utf-8")

    # ---- file / idempotency guards ----

    def test_ddl_file_exists(self):
        self.assertTrue(DDL_FILE.exists(), f"{DDL_FILE} not found")
        self.assertTrue(DDL_FILE.stat().st_size > 0)

    def test_file_is_proposed_not_runnable_blindly(self):
        self.assertIn("STATUS: PROPOSED ONLY", self.sql)
        self.assertIn("MUST NOT be run against production", self.sql)
        sql_only = "\n".join(
            line for line in self.sql.splitlines()
            if not line.strip().startswith("--")
        )
        self.assertNotIn("TRUNCATE", sql_only)
        self.assertNotIn("DROP TABLE", sql_only)
        self.assertNotIn("DROP TABLE", self.sql.replace("DO NOT DROP", ""))

    def test_all_add_column_idempotent(self):
        # Every ALTER ... ADD COLUMN on an existing live table is idempotent.
        sql_only = "\n".join(
            line for line in self.sql.splitlines()
            if not line.strip().startswith("--")
        )
        alter_lines = [
            line.strip()
            for line in sql_only.splitlines()
            if line.strip().startswith("ALTER TABLE ") and " ADD COLUMN " in line
        ]
        self.assertTrue(alter_lines, "expected ADD COLUMN ALTER statements")
        for line in alter_lines:
            self.assertIn("ADD COLUMN IF NOT EXISTS", line, f"non-idempotent ALTER: {line}")

    # ---- gap 1: student_subject_enrollment ----

    def test_enrollment_adds_subject_domain(self):
        self.assertIn(
            "ALTER TABLE student_subject_enrollment ADD COLUMN IF NOT EXISTS subject_domain VARCHAR;",
            self.sql,
        )

    def test_enrollment_adds_subject_skill(self):
        self.assertIn(
            "ALTER TABLE student_subject_enrollment ADD COLUMN IF NOT EXISTS subject_skill VARCHAR;",
            self.sql,
        )

    def test_enrollment_division_still_present(self):
        self.assertIn(
            "ALTER TABLE student_subject_enrollment ADD COLUMN IF NOT EXISTS division VARCHAR;",
            self.sql,
        )

    def test_enrollment_ddl_never_drops_constraints(self):
        # PK (enrollment_record_id), UNIQUE uq_enrollment, and all FKs must stay.
        self.assertNotIn("DROP CONSTRAINT", self.sql)
        self.assertNotIn(
            "ALTER TABLE student_subject_enrollment DROP", self.sql
        )

    # ---- gap 2: faculty_student_map ----

    def test_fsm_adds_mapping_id(self):
        self.assertIn(
            "ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS mapping_id VARCHAR;",
            self.sql,
        )

    def test_fsm_adds_semester_no(self):
        self.assertIn(
            "ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS semester_no INTEGER;",
            self.sql,
        )

    def test_fsm_adds_mapping_type(self):
        self.assertIn(
            "ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS mapping_type VARCHAR;",
            self.sql,
        )

    def test_fsm_adds_is_active(self):
        self.assertIn(
            "ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS is_active BOOLEAN;",
            self.sql,
        )

    def test_fsm_never_touches_mentor_columns(self):
        # mapping_type='MENTOR' is NOT a legal mentor_role CHECK value -> the DDL
        # must NOT alter mentor_role/allocation_reason/mentor_since/status.
        for col in ("mentor_role", "allocation_reason", "mentor_since", "status"):
            self.assertNotIn(
                f"ALTER TABLE faculty_student_map ADD COLUMN IF NOT EXISTS {col}",
                self.sql,
                f"DDL must not re-add/rewrite {col}",
            )
            self.assertNotIn(
                f"ALTER TABLE faculty_student_map ALTER COLUMN {col}",
                self.sql,
            )

    def test_fsm_columns_are_nullable_additive(self):
        idx = self.sql.find("faculty_student_map: extend to carry the new mapping shape")
        section = self.sql[idx:] if idx != -1 else ""
        self.assertTrue(section, "faculty_student_map DDL comment block missing")
        block = self.sql[idx: idx + 2000]
        self.assertIn("do NOT blind-map the new fields", block)
        self.assertNotIn("ADD COLUMN IF NOT EXISTS mapping_id VARCHAR NOT NULL", block)

    def test_fsm_unique_key_documented(self):
        # uq_fac_stu_map (faculty_id, student_id) is preserved; new pairs distinct.
        self.assertIn("uq_fac_stu_map", self.sql)

    # ---- gap 3: career_preferences v2 (ARCHITECTURE B, blocker B4) ----

    def test_career_preferences_v2_table_created(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS career_preferences_v2", self.sql)
        self.assertIn(
            "career_preference_id          VARCHAR NOT NULL PRIMARY KEY", self.sql
        )
        self.assertIn(
            "student_id                    VARCHAR NOT NULL REFERENCES students(student_id)",
            self.sql,
        )
        self.assertIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_career_pref_v2_student",
            self.sql,
        )

    def test_career_preferences_old_table_not_extended_with_new_cols(self):
        # Architecture B: the new columns live on career_preferences_v2, NOT on
        # the old career_preferences (whose M4-contract columns stay intact).
        for col in (
            "primary_interest_domain",
            "secondary_interest_domain",
            "preferred_role",
            "higher_studies_intent",
            "desired_salary_lpa",
            "career_role_category",
            "career_preference_version",
            "role_skill_profile_version",
            "career_preference_source",
        ):
            self.assertNotIn(
                f"ALTER TABLE career_preferences ADD COLUMN IF NOT EXISTS {col}",
                self.sql,
                f"old career_preferences must NOT be extended with {col}",
            )

    def test_no_fabrication_note_present(self):
        # The DDL must document that M4 fields are never fabricated.
        self.assertIn("No fabrication", self.sql)
        self.assertIn("placement_readiness_level", self.sql)

    def test_no_drop_constraint_on_career_preferences(self):
        # The existing NOT NULL constraints on career_preferences are preserved.
        self.assertNotIn(
            "ALTER TABLE career_preferences DROP", self.sql
        )

    # ---- suspension-style ordering / packaging ----

    def test_balanced_parentheses(self):
        """Rough sanity that generated string literals don't poison paren count."""
        sql_only = "\n".join(
            line for line in self.sql.splitlines() if not line.strip().startswith("--")
        )
        self.assertEqual(sql_only.count("("), sql_only.count(")"))


if __name__ == "__main__":
    unittest.main()