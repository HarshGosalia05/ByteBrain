"""Unit tests for StudentResolver and end-to-end Chatbot Scenarios.

Verifies:
  * Token extraction (Student ID, Enrollment ID, Student Name, Pronouns)
  * Stop word filtering and punctuation normalization
  * Single-turn ambiguous queries -> clarification
  * Single-turn specific name/enrollment queries -> resolved
  * Multi-turn follow-up queries with pronouns -> resolved from history
  * Out-of-scope / unauthorized student access -> unauthorized
  * Unknown student name/enrollment -> clarification
  * Student self-scope enforcement
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.schemas.genai import ConversationMessage
from app.services.student_resolver import StudentResolution, StudentResolver


def run(coro):
    return asyncio.run(coro)


class TestStudentResolver(unittest.TestCase):
    def setUp(self):
        self.mock_pool = MagicMock()
        self.mock_faculty_repo = MagicMock()
        self.resolver = StudentResolver(
            pool=self.mock_pool,
            faculty_repo=self.mock_faculty_repo,
        )

    def test_extract_candidate_tokens(self):
        # Case 1: Student ID
        cands = StudentResolver.extract_candidate_tokens("Show marks for STU000007")
        self.assertIn("STU000007", cands)

        # Case 2: Enrollment Number
        cands = StudentResolver.extract_candidate_tokens("Show performance for enrollment 2023010007")
        self.assertIn("2023010007", cands)

        # Case 3: Name with 'for'
        cands = StudentResolver.extract_candidate_tokens("Show performance summary for Jiya Soni")
        self.assertIn("Jiya Soni", cands)

        # Case 4: Name with possessive 's
        cands = StudentResolver.extract_candidate_tokens("Show Jiya Soni's attendance")
        self.assertIn("Jiya Soni", cands)

        # Case 5: Ambiguous query without student
        cands = StudentResolver.extract_candidate_tokens("Show student performance summary")
        self.assertEqual(len(cands), 0)

        # Case 6: Aggregate query
        cands = StudentResolver.extract_candidate_tokens("Show performance summaries for my students")
        self.assertEqual(len(cands), 0)

        # Case 7: Pronoun query
        cands = StudentResolver.extract_candidate_tokens("What about her attendance?")
        self.assertEqual(len(cands), 0)
        self.assertTrue(StudentResolver.has_pronoun_reference("What about her attendance?"))

    def test_student_role_strictly_self_scoped(self):
        res = run(
            self.resolver.resolve(
                role="Student",
                user_context_id="STU101",
                message="What is my SGPA?",
            )
        )
        self.assertEqual(res.status, "RESOLVED")
        self.assertEqual(res.student_id, "STU101")

    def test_faculty_ambiguous_query_returns_no_target_specified(self):
        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show student performance summary",
                intent="student_performance",
            )
        )
        self.assertEqual(res.status, "NO_TARGET_SPECIFIED")
        self.assertIn("Which student would you like", res.clarification_message)

    def test_faculty_explicit_target_id_authorized(self):
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")
        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show performance",
                explicit_target_id="STU007",
            )
        )
        self.assertEqual(res.status, "RESOLVED")
        self.assertEqual(res.student_id, "STU007")

    def test_faculty_explicit_target_id_unauthorized(self):
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value=False)
        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show performance",
                explicit_target_id="STU999",
            )
        )
        self.assertEqual(res.status, "UNAUTHORIZED")
        self.assertIn("outside your authorized scope", res.clarification_message)

    def test_faculty_follow_up_resolved_from_conversation_history(self):
        history = [
            ConversationMessage(role="user", content="Show performance summary for STU007"),
            ConversationMessage(role="assistant", content="STU007 has an SGPA of 8.5."),
        ]
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        # Mock DB find to return student for STU007
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )

        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="What about her attendance?",
                conversation_history=history,
                intent="student_attendance",
            )
        )
    def test_faculty_resolve_by_student_name(self):
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show performance summary for Jiya Soni",
                intent="student_performance",
            )
        )
        self.assertEqual(res.status, "RESOLVED")
        self.assertEqual(res.student_id, "STU000007")
        self.assertEqual(res.first_name, "Jiya")
        self.assertEqual(res.last_name, "Soni")

    def test_faculty_resolve_by_enrollment_no(self):
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show performance for enrollment 2023010007",
                intent="student_performance",
            )
        )
        self.assertEqual(res.status, "RESOLVED")
        self.assertEqual(res.student_id, "STU000007")

    def test_faculty_unknown_student_returns_not_found(self):
        self.resolver._find_students_in_db = AsyncMock(return_value=[])

        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show performance for John Doe",
                intent="student_performance",
            )
        )
        self.assertEqual(res.status, "NOT_FOUND")
        self.assertIn("couldn't find a student matching 'John Doe'", res.clarification_message)

    def test_faculty_ambiguous_multiple_matches_returns_ambiguous(self):
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                },
                {
                    "student_id": "STU000060",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023020010,
                    "department_code": 2,
                },
            ]
        )
        # Both reachable for this faculty
        self.mock_faculty_repo.student_is_reachable = AsyncMock(return_value="class")

        res = run(
            self.resolver.resolve(
                role="Faculty",
                user_context_id="FAC001",
                message="Show performance for Jiya Soni",
                intent="student_performance",
            )
        )
        self.assertEqual(res.status, "AMBIGUOUS")
        self.assertIn("multiple students matching 'Jiya Soni'", res.clarification_message)

    def test_admin_resolve_student(self):
        self.resolver._find_students_in_db = AsyncMock(
            return_value=[
                {
                    "student_id": "STU000007",
                    "first_name": "Jiya",
                    "last_name": "Soni",
                    "enrollment_no": 2023010007,
                    "department_code": 1,
                }
            ]
        )

        res = run(
            self.resolver.resolve(
                role="Admin",
                user_context_id="ADM001",
                message="Show performance for Jiya Soni",
                intent="student_performance",
            )
        )
        self.assertEqual(res.status, "RESOLVED")
        self.assertEqual(res.student_id, "STU000007")


if __name__ == "__main__":
    unittest.main()
