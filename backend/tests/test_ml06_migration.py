"""Migration/schema validation tests for ML-06 (migrations/21_ml_predictions.sql).

Validates the migration file contents against the approved persistence
design without touching a live database:
  * dedicated ml_predictions table (not risk_predictions)
  * required identification/metadata columns
  * FK, CHECK, index and timestamp conventions
  * NULL preservation (no COALESCE / fake-zero defaults)
  * risk_predictions is never referenced
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_FILE = MIGRATIONS_DIR / "21_ml_predictions.sql"


class TestMigrationFile(unittest.TestCase):
    def setUp(self):
        self.sql = MIGRATION_FILE.read_text(encoding="utf-8")

    def test_migration_file_exists(self):
        self.assertTrue(MIGRATION_FILE.exists(), f"{MIGRATION_FILE} not found")
        self.assertTrue(MIGRATION_FILE.stat().st_size > 0)

    def test_correct_sequence_number(self):
        numbered = sorted(
            p for p in MIGRATIONS_DIR.glob("[0-9]*.sql")
        )
        # ML-12 adds 22_prediction_feedback.sql after the ML-06 migration.
        self.assertIn("22_prediction_feedback.sql", [p.name for p in numbered])
        self.assertEqual(numbered[-1].name, "22_prediction_feedback.sql")

    def test_creates_dedicated_table(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS ml_predictions", self.sql)

    def test_required_columns_present(self):
        for col in (
            "prediction_id",
            "student_id",
            "prediction_type",
            "model_version",
            "prediction_value",
            "input_row_count",
            "prediction_count",
            "generated_at",
            "created_at",
        ):
            self.assertRegex(self.sql, rf"\b{col}\b", f"missing column {col}")

    def test_prediction_id_is_uuid_pk(self):
        self.assertIn("prediction_id    uuid PRIMARY KEY DEFAULT gen_random_uuid()", self.sql)

    def test_student_id_not_null_with_fk(self):
        self.assertIn("student_id       varchar NOT NULL REFERENCES students(student_id)", self.sql)

    def test_prediction_type_check_constraint(self):
        self.assertIn(
            "prediction_type  varchar NOT NULL CHECK (prediction_type IN ('m1', 'm2', 'm3', 'm4'))",
            self.sql,
        )

    def test_prediction_value_jsonb_not_null(self):
        self.assertIn("prediction_value jsonb NOT NULL", self.sql)

    def test_timestamp_conventions(self):
        self.assertIn("generated_at     timestamptz NOT NULL DEFAULT now()", self.sql)
        self.assertIn("created_at       timestamptz NOT NULL DEFAULT now()", self.sql)

    def test_model_version_nullable(self):
        # model_version has no NOT NULL -> NULL semantics preserved
        self.assertRegex(
            self.sql,
            r"model_version\s+varchar(?!\s+NOT NULL)",
        )

    def test_required_indexes(self):
        self.assertIn(
            "idx_ml_predictions_student_type_generated",
            self.sql,
        )
        self.assertIn(
            "ON ml_predictions (student_id, prediction_type, generated_at DESC)",
            self.sql,
        )

    def test_risk_predictions_untouched(self):
        # The migration must never read/write/reference risk_predictions in
        # any actual SQL statement (comments are documentation only).
        sql_only = "\n".join(
            line for line in self.sql.splitlines()
            if not line.strip().startswith("--")
        )
        for keyword in ("risk_predictions", "ALTER", "UPDATE", "DELETE", "DROP", "TRUNCATE"):
            self.assertNotIn(keyword, sql_only, f"migration must not use {keyword}")

    def test_no_fake_zero_defaults(self):
        # Missing values must remain NULL; nothing may default to 0.
        for bad in ("DEFAULT 0", "DEFAULT '0'", "COALESCE", "IS NOT NULL OR 0"):
            self.assertNotIn(bad, self.sql)

    def test_idempotent_ddl(self):
        for stmt in (
            "CREATE TABLE IF NOT EXISTS ml_predictions",
            "CREATE INDEX IF NOT EXISTS idx_ml_predictions_student_type_generated",
        ):
            self.assertIn(stmt, self.sql)

    def test_balanced_parentheses(self):
        self.assertEqual(self.sql.count("("), self.sql.count(")"))


if __name__ == "__main__":
    unittest.main()
