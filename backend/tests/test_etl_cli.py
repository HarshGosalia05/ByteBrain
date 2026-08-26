"""Unit tests for the ETL CLI argument parsing and command behavior.

Uses the standard library ``unittest`` with stdout capture; the dry-run
command path never touches a database.
"""

import contextlib
import io
import unittest

from etl import cli
from etl.exceptions import EXIT_LOAD_DERIVE_FAILURE, EXIT_SUCCESS
from etl.stages import STAGE_NAMES


class TestCliParsing(unittest.TestCase):
    def test_run_defaults_to_dry_run(self):
        args = cli.build_parser().parse_args(["run"])
        self.assertEqual(args.command, "run")
        self.assertFalse(args.apply)
        self.assertFalse(args.dry_run)
        self.assertEqual(args.sources, "")

    def test_run_apply_flag(self):
        args = cli.build_parser().parse_args(["run", "--apply"])
        self.assertTrue(args.apply)
        self.assertFalse(args.dry_run)

    def test_run_dry_and_apply_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.build_parser().parse_args(["run", "--apply", "--dry-run"])
        self.assertEqual(ctx.exception.code, 2)

    def test_run_all_options(self):
        parser = cli.build_parser()
        args = parser.parse_args(
            [
                "run",
                "--sources", "daily_attendance,weekly_timetable",
                "--run-id", "run-123",
                "--pipeline-version", "2.0.0",
                "--environment", "production",
                "--log-level", "DEBUG",
            ]
        )
        self.assertEqual(args.sources, "daily_attendance,weekly_timetable")
        self.assertEqual(args.run_id, "run-123")
        self.assertEqual(args.pipeline_version, "2.0.0")
        self.assertEqual(args.environment, "production")
        self.assertEqual(args.log_level, "DEBUG")

    def test_stage_choices_are_canonical_names(self):
        parser = cli.build_parser()
        for name in STAGE_NAMES:
            args = parser.parse_args(["run", "--stage", name])
            self.assertEqual(args.stage, name)

    def test_stages_command(self):
        args = cli.build_parser().parse_args(["stages"])
        self.assertEqual(args.command, "stages")

    def test_invalid_command_rejected(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["bogus"])


class TestCliCommands(unittest.TestCase):
    def capture(self, func):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = func()
        return code, out.getvalue(), err.getvalue()

    def test_stages_lists_contract(self):
        code, out, _ = self.capture(lambda: cli.main(["stages"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertEqual([line for line in out.splitlines() if line], list(STAGE_NAMES))

    def test_stages_json(self):
        code, out, _ = self.capture(lambda: cli.main(["stages", "--json"]))
        self.assertEqual(code, EXIT_SUCCESS)
        import json
        self.assertEqual(json.loads(out), list(STAGE_NAMES))

    def test_run_dry_run_success_no_db(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--dry-run"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("mode=dry-run", out)
        self.assertIn("exit_code=0", out)
        self.assertIn("run_id=", out)

    def test_run_default_mode_is_dry_run(self):
        code, out, _ = self.capture(lambda: cli.main(["run"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("mode=dry-run", out)

    def test_run_derive_stage_implemented(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "derive"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("derive: status=success", out)

    def test_run_stitch_stage_implemented(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "stitch"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("stitch: status=success", out)

    def test_run_transform_stage_implemented(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "transform"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("transform: status=success", out)

    def test_run_load_stage_implemented(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "load"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("load: status=success", out)

    def test_run_help_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["run", "--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
