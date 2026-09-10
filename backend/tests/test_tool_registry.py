"""G1 Tool Registry tests.

Verifies the allowlist-only catalog: registration, duplicate/conflict
rejection, fail-closed lookups, the Student / Faculty / Admin role/tool
matrix, cross-role denial, role-scoped intent resolution, and that tool
definitions can never carry callables, import paths, SQL, or DB access.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pydantic import ValidationError

from app.schemas.tools import ToolDefinition
from app.services.tool_registry import (
    ToolRegistry,
    ToolRegistryError,
    build_default_registry,
)


def _make_tool(
    tool_name: str = "test_tool",
    intents=None,
    allowed_roles=None,
    scope: str = "own_student",
    **kwargs,
) -> ToolDefinition:
    return ToolDefinition(
        tool_name=tool_name,
        description="Test tool",
        intents=intents or ["attendance"],
        allowed_roles=allowed_roles or ["Student"],
        category="analytics",
        scope=scope,
        analytics_backed=True,
        **kwargs,
    )


class TestToolRegistry(unittest.TestCase):
    def test_register_and_retrieve_tool(self):
        registry = ToolRegistry()
        tool = _make_tool(tool_name="registry_test_tool")
        registry.register(tool)
        self.assertIs(registry.get("registry_test_tool"), tool)
        self.assertTrue(registry.has("registry_test_tool"))

    def test_unknown_tool_fails_closed(self):
        registry = build_default_registry()
        self.assertIsNone(registry.get("no_such_tool"))
        self.assertFalse(registry.has("no_such_tool"))
        self.assertFalse(registry.is_allowed("no_such_tool", "Student"))

    def test_duplicate_tool_rejected(self):
        registry = ToolRegistry()
        registry.register(_make_tool(tool_name="dup_tool"))
        with self.assertRaises(ToolRegistryError):
            registry.register(_make_tool(tool_name="dup_tool"))

    def test_intent_role_conflict_rejected(self):
        registry = ToolRegistry()
        registry.register(_make_tool(tool_name="first_tool"))
        with self.assertRaises(ToolRegistryError):
            registry.register(
                _make_tool(
                    tool_name="second_tool",
                    intents=["attendance"],
                    allowed_roles=["Student"],
                )
            )

    def test_arbitrary_object_cannot_be_registered(self):
        registry = ToolRegistry()
        with self.assertRaises(ToolRegistryError):
            registry.register(lambda: None)  # type: ignore[arg-type]

    def test_unknown_role_intent_resolution_returns_none(self):
        registry = build_default_registry()
        self.assertIsNone(registry.tool_for_intent("attendance", "Admin"))


class TestDefaultCatalogRoleMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_default_registry()

    def test_catalog_has_19_tools_all_implemented(self):
        names = self.registry.tool_names
        self.assertEqual(len(names), 19)
        all_tools = [
            tool
            for role in ("Student", "Faculty", "Admin")
            for tool in self.registry.tools_for_role(role)
        ]
        self.assertEqual(len(all_tools), 19)
        implemented = [tool for tool in all_tools if tool.implemented]
        self.assertEqual(len(implemented), 19)

    def test_student_gets_own_7_tools_only(self):
        names = {t.tool_name for t in self.registry.tools_for_role("Student")}
        self.assertEqual(len(names), 7)
        for expected in (
            "student_profile_tool",
            "student_timetable_tool",
            "student_academic_performance_tool",
            "student_attendance_tool",
            "student_subject_analysis_tool",
            "student_prediction_explanation_tool",
            "student_career_coach_tool",
        ):
            self.assertIn(expected, names)

    def test_faculty_gets_7_tools_only(self):
        names = {t.tool_name for t in self.registry.tools_for_role("Faculty")}
        self.assertEqual(len(names), 7)
        for expected in (
            "faculty_student_analytics_tool",
            "faculty_subject_analytics_tool",
            "faculty_flagged_students_tool",
            "faculty_prediction_insights_tool",
            "faculty_department_analytics_tool",
            "faculty_timetable_tool",
            "faculty_mentees_tool",
        ):
            self.assertIn(expected, names)

    def test_admin_gets_5_tools_only(self):
        names = {t.tool_name for t in self.registry.tools_for_role("Admin")}
        self.assertEqual(len(names), 5)
        for expected in (
            "admin_institution_analytics_tool",
            "admin_department_analytics_tool",
            "admin_trends_analytics_tool",
            "admin_flagged_students_tool",
            "admin_ml_insights_tool",
        ):
            self.assertIn(expected, names)

    def test_student_cannot_access_faculty_or_admin_tools(self):
        self.assertFalse(
            self.registry.is_allowed("faculty_student_analytics_tool", "Student")
        )
        self.assertFalse(
            self.registry.is_allowed("admin_institution_analytics_tool", "Student")
        )

    def test_faculty_cannot_access_admin_tools(self):
        self.assertFalse(
            self.registry.is_allowed("admin_institution_analytics_tool", "Faculty")
        )

    def test_admin_cannot_access_student_or_faculty_tools(self):
        self.assertFalse(self.registry.is_allowed("student_attendance_tool", "Admin"))
        self.assertFalse(
            self.registry.is_allowed("faculty_student_analytics_tool", "Admin")
        )

    def test_shared_intent_resolves_per_role(self):
        faculty_tool = self.registry.tool_for_intent("department_analytics", "Faculty")
        admin_tool = self.registry.tool_for_intent("department_analytics", "Admin")
        self.assertEqual(faculty_tool.tool_name, "faculty_department_analytics_tool")
        self.assertEqual(admin_tool.tool_name, "admin_department_analytics_tool")
        flagged = self.registry.tool_for_intent("flagged_students", "Faculty")
        self.assertEqual(flagged.tool_name, "faculty_flagged_students_tool")


class TestToolDefinitionSafety(unittest.TestCase):
    def test_tool_definition_rejects_unknown_fields(self):
        with self.assertRaises(ValidationError):
            ToolDefinition(
                tool_name="evil_tool",
                description="x",
                intents=["attendance"],
                allowed_roles=["Student"],
                category="analytics",
                scope="own_student",
                analytics_backed=True,
                import_path="os.system",  # type: ignore[call-arg]
            )

    def test_tool_definition_has_no_callable_or_sql_fields(self):
        forbidden = {
            "exec",
            "eval",
            "import_path",
            "module",
            "handler",
            "callable",
            "sql",
            "query",
            "db",
            "session",
            "pool",
            "repository",
            "connection",
        }
        fields = set(ToolDefinition.model_fields)
        self.assertTrue(forbidden.isdisjoint(fields))

    def test_tool_definition_requires_backing_declaration(self):
        with self.assertRaises(ValidationError):
            ToolDefinition(
                tool_name="unbacked_tool",
                description="x",
                intents=["attendance"],
                allowed_roles=["Student"],
                category="analytics",
                scope="own_student",
            )

    def test_scope_requirements_synced(self):
        student_tool = _make_tool(scope="own_student")
        self.assertTrue(student_tool.requires_student_scope)
        self.assertFalse(student_tool.requires_department_scope)
        dept_tool = _make_tool(
            tool_name="dept_tool",
            allowed_roles=["Faculty"],
            scope="department_scope",
        )
        self.assertTrue(dept_tool.requires_department_scope)


if __name__ == "__main__":
    unittest.main()
