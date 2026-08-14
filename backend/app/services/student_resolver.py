"""Authoritative student identity resolver for GenAI Chatbot.

Resolves student entities (student IDs, enrollment numbers, names, and pronouns)
from user messages, conversation history, and request parameters against the database
with strict role-based access control (RBAC):
  * Student: Strictly restricted to their own authenticated identity.
  * Faculty: Restricted to students enrolled in their classes or assigned as mentees.
  * Admin: Institution-wide access to student profiles.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

import asyncpg

from app.repositories.faculty_repo import FacultyRepository
from app.schemas.genai import ConversationMessage, UserRole

logger = logging.getLogger(__name__)

ResolutionStatus = Literal[
    "RESOLVED",
    "AMBIGUOUS",
    "NOT_FOUND",
    "UNAUTHORIZED",
    "NO_TARGET_SPECIFIED",
]


@dataclass(frozen=True)
class StudentResolution:
    """Outcome of student identity resolution."""

    status: ResolutionStatus
    student_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    enrollment_no: Optional[int] = None
    department_code: Optional[int] = None
    clarification_message: Optional[str] = None


STOP_WORDS = {
    "a", "an", "the", "this", "that", "these", "those", "all",
    "my", "our", "your", "his", "her", "their", "its", "him", "she", "he",
    "student", "students", "class", "classes", "subject", "subjects",
    "performance", "attendance", "risk", "marks", "grade", "grades",
    "prediction", "predictions", "summary", "summaries", "overview", "analytics",
    "report", "details", "record",
    "who", "what", "which", "where", "when", "why", "how",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had",
    "show", "tell", "give", "display", "check", "view", "find",
    "about", "for", "of", "with", "in", "on", "at", "to", "from",
    "enrollment", "number", "id", "roll", "university", "sgpa", "cgpa", "gpa",
    "now", "also", "please", "can", "could", "would", "will", "status", "insight", "insights",
}

PRONOUN_PATTERN = re.compile(
    r"\b(her|his|their|him|she|he|this student|that student|the student)\b",
    re.IGNORECASE,
)


class StudentResolver:
    """Authoritative student identity resolver."""

    def __init__(self, pool: Optional[asyncpg.Pool], faculty_repo: Optional[Any] = None) -> None:
        self.pool = pool
        self._faculty_repo = faculty_repo or (FacultyRepository(pool) if pool else None)

    @classmethod
    def extract_candidate_tokens(cls, text: str) -> list[str]:
        """Extract candidate student identifiers (IDs, enrollment numbers, names) from text."""
        candidates: list[str] = []
        cleaned = text.strip()

        # 1. Student ID pattern (e.g. STU000007, STU001)
        for m in re.finditer(r"\b(STU\d+)\b", cleaned, re.IGNORECASE):
            candidates.append(m.group(1).upper())

        # 2. Enrollment number pattern (e.g. 2023010007 or 10-digit number)
        for m in re.finditer(r"\b(202\d{7}|\d{10})\b", cleaned):
            candidates.append(m.group(1))

        # 3. Targeted naming phrases
        patterns = [
            r"(?:for|of|about)\s+(?:student\s+)?(?:enrollment\s*(?:no\.?|id|number)?\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)?)",
            r"([A-Za-z]+(?:\s+[A-Za-z]+)?)(?:'s|’s)\s+(?:performance|attendance|marks|risk|sgpa|cgpa|gpa|result|report)",
            r"(?:how is|how's|status of)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, cleaned, re.IGNORECASE):
                raw = re.sub(r"[^\w\s]", " ", m.group(1)).strip()
                words = [w for w in raw.split() if w.lower() not in STOP_WORDS]
                if words:
                    cand = " ".join(words)
                    if len(cand) >= 2:
                        candidates.append(cand)

        # 4. Short direct answer (e.g. after clarification prompt: "Jiya Soni", "2023010007")
        normalized_words = [
            w
            for w in re.sub(r"[^\w\s]", " ", cleaned).split()
            if w.lower() not in STOP_WORDS
        ]
        if 1 <= len(normalized_words) <= 3:
            cand = " ".join(normalized_words)
            if len(cand) >= 2 and not PRONOUN_PATTERN.search(cand):
                candidates.append(cand)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in candidates:
            k = c.lower()
            if k not in seen:
                seen.add(k)
                unique.append(c)
        return unique

    @classmethod
    def has_pronoun_reference(cls, text: str) -> bool:
        """Check if message refers to a previously discussed student via pronoun."""
        return bool(PRONOUN_PATTERN.search(text))

    async def _find_students_in_db(self, token: str) -> list[dict]:
        """Lookup students in DB by ID, enrollment_no, or name."""
        if not self.pool:
            return []

        token_clean = token.strip()
        if not token_clean:
            return []

        async with self.pool.acquire() as conn:
            # 1. Exact student_id match
            if re.match(r"^STU\d+$", token_clean, re.IGNORECASE):
                rows = await conn.fetch(
                    """
                    SELECT student_id, first_name, last_name, enrollment_no, department_code
                    FROM students
                    WHERE UPPER(student_id) = UPPER($1)
                    """,
                    token_clean,
                )
                if rows:
                    return [dict(r) for r in rows]

            # 2. Exact enrollment_no match
            if token_clean.isdigit():
                try:
                    enr_val = int(token_clean)
                    rows = await conn.fetch(
                        """
                        SELECT student_id, first_name, last_name, enrollment_no, department_code
                        FROM students
                        WHERE enrollment_no = $1
                        """,
                        enr_val,
                    )
                    if rows:
                        return [dict(r) for r in rows]
                except ValueError:
                    pass

            # 3. Name matching
            parts = token_clean.split()
            if len(parts) >= 2:
                first, last = parts[0], parts[-1]
                rows = await conn.fetch(
                    """
                    SELECT student_id, first_name, last_name, enrollment_no, department_code
                    FROM students
                    WHERE (first_name ILIKE $1 AND last_name ILIKE $2)
                       OR (first_name ILIKE $2 AND last_name ILIKE $1)
                       OR (full_name ILIKE $3)
                    """,
                    first,
                    last,
                    f"%{token_clean}%",
                )
                if rows:
                    return [dict(r) for r in rows]

            # Single word: first_name or last_name match
            rows = await conn.fetch(
                """
                SELECT student_id, first_name, last_name, enrollment_no, department_code
                FROM students
                WHERE first_name ILIKE $1 OR last_name ILIKE $1
                """,
                f"{token_clean}%",
            )
            return [dict(r) for r in rows]

    async def resolve(
        self,
        *,
        role: UserRole,
        user_context_id: str,
        message: str,
        conversation_history: list[ConversationMessage] | None = None,
        explicit_target_id: str | None = None,
        intent: str | None = None,
    ) -> StudentResolution:
        """Resolve authoritative target student with RBAC validation."""
        # 1. Student role is strictly self-scoped to the authenticated token identity
        if role == "Student":
            cands = self.extract_candidate_tokens(message)
            for cand in cands:
                if self.pool:
                    db_matches = await self._find_students_in_db(cand)
                    for m in db_matches:
                        if m["student_id"] != user_context_id:
                            return StudentResolution(
                                status="UNAUTHORIZED",
                                clarification_message="You are only authorized to view your own academic information.",
                            )
                elif re.match(r"^STU\d+$", cand, re.IGNORECASE) and cand.upper() != user_context_id.upper():
                    return StudentResolution(
                        status="UNAUTHORIZED",
                        clarification_message="You are only authorized to view your own academic information.",
                    )
            return StudentResolution(status="RESOLVED", student_id=user_context_id)

        # 2. If explicit target student ID is provided in request
        if explicit_target_id:
            if self.pool:
                db_matches = await self._find_students_in_db(explicit_target_id)
                if db_matches:
                    matched_student = db_matches[0]
                    if role == "Faculty" and self._faculty_repo:
                        reach = await self._faculty_repo.student_is_reachable(
                            user_context_id, matched_student["student_id"]
                        )
                        if not reach:
                            return StudentResolution(
                                status="UNAUTHORIZED",
                                clarification_message="That student is outside your authorized scope.",
                            )
                    return StudentResolution(
                        status="RESOLVED",
                        student_id=matched_student["student_id"],
                        first_name=matched_student["first_name"],
                        last_name=matched_student["last_name"],
                        enrollment_no=matched_student["enrollment_no"],
                        department_code=matched_student["department_code"],
                    )
            # If no DB pool (e.g. mock environment) or tool-level enforcement
            if role == "Faculty" and self._faculty_repo:
                reach = await self._faculty_repo.student_is_reachable(
                    user_context_id, explicit_target_id
                )
                if reach is False:
                    return StudentResolution(
                        status="UNAUTHORIZED",
                        clarification_message="That student is outside your authorized scope.",
                    )
            return StudentResolution(
                status="RESOLVED",
                student_id=explicit_target_id,
            )

        # 3. Extract candidate tokens from current message
        current_candidates = self.extract_candidate_tokens(message)

        # 4. If no candidate in current message, but history exists and pronoun or follow-up
        if not current_candidates and conversation_history:
            for prev_msg in reversed(conversation_history[-6:]):
                hist_cands = self.extract_candidate_tokens(prev_msg.content)
                if hist_cands:
                    current_candidates = hist_cands
                    break

        # 5. If still no candidates found
        if not current_candidates:
            topic = "performance summary"
            if intent in ("student_attendance", "attendance"):
                topic = "attendance details"
            elif intent in ("prediction_insights", "prediction_explanation"):
                topic = "prediction insights"
            return StudentResolution(
                status="NO_TARGET_SPECIFIED",
                clarification_message=(
                    f"Sure. Which student would you like the {topic} for? "
                    "Please provide the student's name or enrollment ID."
                ),
            )

        # 6. Try resolving candidates against DB
        for cand in current_candidates:
            db_matches = await self._find_students_in_db(cand)
            if not db_matches:
                continue

            if role == "Faculty":
                # Filter by reachability
                authorized_matches = []
                for m in db_matches:
                    if self._faculty_repo:
                        reach = await self._faculty_repo.student_is_reachable(
                            user_context_id, m["student_id"]
                        )
                        if reach:
                            authorized_matches.append(m)
                    else:
                        authorized_matches.append(m)

                if len(authorized_matches) == 1:
                    m = authorized_matches[0]
                    return StudentResolution(
                        status="RESOLVED",
                        student_id=m["student_id"],
                        first_name=m["first_name"],
                        last_name=m["last_name"],
                        enrollment_no=m["enrollment_no"],
                        department_code=m["department_code"],
                    )
                if len(authorized_matches) > 1:
                    opts = ", ".join(
                        f"{m['first_name']} {m['last_name']} (Enrollment {m['enrollment_no']})"
                        for m in authorized_matches
                    )
                    return StudentResolution(
                        status="AMBIGUOUS",
                        clarification_message=(
                            f"I found multiple students matching '{cand}' in your classes: {opts}. "
                            "Please specify the enrollment ID."
                        ),
                    )
                # Found in DB but not authorized for this faculty
                return StudentResolution(
                    status="UNAUTHORIZED",
                    clarification_message="That student is outside your authorized scope.",
                )

            if role == "Admin":
                if len(db_matches) == 1:
                    m = db_matches[0]
                    return StudentResolution(
                        status="RESOLVED",
                        student_id=m["student_id"],
                        first_name=m["first_name"],
                        last_name=m["last_name"],
                        enrollment_no=m["enrollment_no"],
                        department_code=m["department_code"],
                    )
                opts = ", ".join(
                    f"{m['first_name']} {m['last_name']} (Enrollment {m['enrollment_no']})"
                    for m in db_matches[:5]
                )
                return StudentResolution(
                    status="AMBIGUOUS",
                    clarification_message=(
                        f"I found multiple students matching '{cand}': {opts}. "
                        "Please specify the enrollment ID."
                    ),
                )

        # If candidates were extracted from message but not found in DB
        first_cand = current_candidates[0]
        return StudentResolution(
            status="NOT_FOUND",
            clarification_message=(
                f"I couldn't find a student matching '{first_cand}'. "
                "Please check the spelling or provide their enrollment ID."
            ),
        )
