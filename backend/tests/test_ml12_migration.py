"""Migration/schema validation tests for ML-12 (migrations/22_prediction_feedback.sql).

Validates the migration file contents against the approved ML-12 feedback
design without touching a live database:
  * append-only prediction_feedback table (never updates/deletes predictions)
  * FKs to ml_predictions(prediction_id) and students(student_id)
  * faculty_id is a plain varchar (NO FK), matching the out-of-band faculty
    DDL convention from 20_faculty_notifications.sql
  * feedback_action CHECK limited to 'confirmed'/'dismissed'
  * NULL preservation (no COALESCE / fake-zero defaults)
  * index and timestamp conventions
"""

from __future__ import annotations

import unittest
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_FILE = MIGRATIONS_DIR / "22_prediction_feedback.sql"


class TestMigrationFile(unittest.TestCase):
    def setUp(self):
        self.sql = MIGRATION_FILE.read_text(encoding="utf-8")

    def test_migration_file_exists(self):
        self.assertTrue(MIGRATION_FILE.exists(), f"{MIGRATION_FILE} not found")
        self.assertTrue(MIGRATION_FILE.stat().st_size > 0)

    def test_creates_dedicated_table(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS prediction_feedback", self.sql)

    def test_required_columns_present(self):
        for col in (
            "feedback_id",
            "prediction_id",
            "student_id",
            "faculty_id",
            "feedback_action",
            "note",
            "model_version",
            "feedback_timestamp",
            "created_at",
        ):
            self.assertRegex(self.sql, rf"\b{col}\b", f"missing column {col}")

    def test_feedback_id_is_uuid_pk(self):
        self.assertIn("feedback_id       uuid PRIMARY KEY DEFAULT gen_random_uuid()", self.sql)

    def test_prediction_id_not_null_with_fk(self):
        self.assertIn(
            "prediction_id     uuid NOT NULL REFERENCES ml_predictions(prediction_id)",
            self.sql,
        )

    def test_student_id_not_null_with_fk(self):
        self.assertIn(
            "student_id        varchar NOT NULL REFERENCES students(student_id)",
            self.sql,
        )

    def test_faculty_id_plain_varchar_no_fk(self):
        # faculty DDL is out-of-band; follow the 20_faculty_notifications.sql
        # convention of a plain varchar, never a fabricated FK.
        self.assertRegex(self.sql, r"faculty_id\s+varchar NOT NULL(?!\s+REFERENCES)")
        self.assertNotIn("REFERENCES faculty", self.sql)

    def test_feedback_action_check_constraint(self):
        self.assertIn(
            "feedback_action   varchar NOT NULL CHECK (feedback_action IN ('confirmed', 'dismissed'))",
            self.sql,
        )

    def test_note_and_model_version_nullable(self):
        self.assertRegex(self.sql, r"note\s+text(?!\s+NOT NULL)")
        self.assertRegex(self.sql, r"model_version\s+varchar(?!\s+NOT NULL)")

    def test_timestamp_conventions(self):
        self.assertIn("feedback_timestamp timestamptz NOT NULL DEFAULT now()", self.sql)
        self.assertIn("created_at        timestamptz NOT NULL DEFAULT now()", self.sql)

    def test_required_indexes(self):
        for idx in (
            "idx_prediction_feedback_prediction",
            "idx_prediction_feedback_student",
            "idx_prediction_feedback_faculty",
        ):
            self.assertIn(idx, self.sql)
        self.assertIn(
            "ON prediction_feedback (prediction_id, feedback_timestamp DESC)",
            self.sql,
        )
        self.assertIn(
            "ON prediction_feedback (student_id, feedback_timestamp DESC)",
            self.sql,
        )

    def test_predictions_untouched(self):
        # The migration must never modify an existing prediction.
        sql_only = "\n".join(
            line for line in self.sql.splitlines()
            if not line.strip().startswith("--")
        )
        for keyword in ("ALTER", "UPDATE", "DELETE", "DROP", "TRUNCATE"):
            self.assertNotIn(keyword, sql_only, f"migration must not use {keyword}")

    def test_risk_predictions_never_referenced(self):
        sql_only = "\n".join(
            line for line in self.sql.splitlines()
            if not line.strip().startswith("--")
        )
        self.assertNotIn("risk_predictions", sql_only)

    def test_no_fake_zero_defaults(self):
        for bad in ("DEFAULT 0", "DEFAULT '0'", "COALESCE", "IS NOT NULL OR 0"):
            self.assertNotIn(bad, self.sql)

    def test_idempotent_ddl(self):
        for stmt in (
            "CREATE TABLE IF NOT EXISTS prediction_feedback",
            "CREATE INDEX IF NOT EXISTS idx_prediction_feedback_prediction",
            "CREATE INDEX IF NOT EXISTS idx_prediction_feedback_student",
            "CREATE INDEX IF NOT EXISTS idx_prediction_feedback_faculty",
        ):
            self.assertIn(stmt, self.sql)

    def test_no_unique_key_on_review(self):
        # Append-only: re-review inserts a new row; there is no UNIQUE key
        # on (prediction_id, faculty_id) — latest verdict is resolved at read.
        self.assertNotIn("UNIQUE (prediction_id, faculty_id)", self.sql)

    def test_balanced_parentheses(self):
        self.assertEqual(self.sql.count("("), self.sql.count(")"))


if __name__ == "__main__":
    unittest.main()
