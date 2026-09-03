"""Pydantic shapes for authored question content (math, coding, mcq, coding_mcq).

Contract: docs/QUESTION_CONTENT_FORMAT.md

These validate JSON files under ``data/questions/**`` before the loader turns them into
items for the existing quiz engine. They describe *authored content only* — the runtime
session/SRS shapes stay in ``backend/quiz/handler.py`` and ``ReviewCard``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

SCHEMA_VERSION = 1

QuestionKind = Literal["mcq", "coding", "math", "vocab", "coding_mcq"]
"""Practice item kinds the Questions surface knows about.

Authored content files use ``math``, ``coding``, ``mcq``, and ``coding_mcq``.
``vocab`` stays in the GRE word bank.
"""

CONTENT_KINDS: tuple[str, ...] = ("math", "coding", "mcq", "coding_mcq")

Difficulty = Literal["easy", "medium", "hard"]

_TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_NOTE_TOPIC_RE = re.compile(r"^(?:L|MT)\d+-T\d+$", re.IGNORECASE)


class ContentTopic(BaseModel):
    """Roadmap position + lecture-note linkage for one content file."""

    model_config = ConfigDict(extra="allow")

    topic_id: str = Field(..., min_length=2, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    stage: str = Field(default="", max_length=60)
    path: list[str] = Field(default_factory=list)
    track: str = Field(default="", max_length=60)
    prerequisites: list[str] = Field(default_factory=list)
    note_topic_ids: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=600)

    @field_validator("topic_id")
    @classmethod
    def _slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not _TOPIC_ID_RE.match(v):
            raise ValueError(f"topic_id must match [a-z0-9._-]: {v!r}")
        return v

    @field_validator("note_topic_ids")
    @classmethod
    def _note_topics(cls, v: list[str]) -> list[str]:
        out = []
        for raw in v:
            tag = str(raw).strip().upper()
            if not tag:
                continue
            if not _NOTE_TOPIC_RE.match(tag):
                raise ValueError(f"note_topic_ids entries must look like L4-T02 or MT1-T02: {raw!r}")
            out.append(tag)
        return out


class TestCase(BaseModel):
    """One coding test case. Call mode uses input/expected_output; script mode uses stdin."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", max_length=120)
    input: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    expected_output: Any = None
    stdin: str | None = None
    expected_stdout: str | None = None
    is_edge_case: bool = False
    description: str = Field(default="", max_length=600)
    hidden: bool = False

    @property
    def is_script_mode(self) -> bool:
        return self.expected_stdout is not None


class MathQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1, max_length=160)
    problem: str = Field(..., min_length=1)
    # Empty answer = open / proof-style (self-check; no auto-grade key).
    answer: str = Field(default="", max_length=2000)
    answer_format: Literal["number", "expression", "text", "open"] = "expression"
    solution_steps: list[str] = Field(default_factory=list)
    difficulty: Difficulty = "medium"
    explanation: str = ""
    hint: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _open_if_no_answer(self) -> MathQuestion:
        if not (self.answer or "").strip() and self.answer_format != "open":
            self.answer_format = "open"
        return self


class McqQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(..., min_length=1, max_length=160)
    question: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2)
    answer_index: int = Field(..., ge=0)
    difficulty: Difficulty = "medium"
    explanation: str = ""
    hint: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _idx(self) -> McqQuestion:
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index out of range")
        return self


class CodingMcqQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(..., min_length=1, max_length=160)
    prompt: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2)
    answer_index: int = Field(..., ge=0)
    starter_code: str = ""
    difficulty: Difficulty = "medium"
    explanation: str = ""
    hint: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _idx(self) -> CodingMcqQuestion:
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index out of range")
        return self


class CodingQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1, max_length=160)
    title: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1)
    language: str = Field(default="python", max_length=32)
    entry_point: str = Field(default="", max_length=120)
    starter_code: str = ""
    solution: str = ""
    setup_code: str = ""
    difficulty: Difficulty = "medium"
    explanation: str = ""
    hint: str = ""
    tags: list[str] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def _check_modes(self) -> CodingQuestion:
        for i, case in enumerate(self.test_cases):
            if not self.entry_point and case.expected_stdout is None:
                raise ValueError(
                    f"{self.id}: test case {i} needs expected_stdout when entry_point is unset"
                )
        return self


class ContentFile(BaseModel):
    """One authored topic file: ``data/questions/<kind>/**/<topic>.json``."""

    model_config = ConfigDict(extra="allow")

    schema_version: int = SCHEMA_VERSION
    kind: Literal["math", "coding", "mcq", "coding_mcq"]
    topic: ContentTopic
    questions: list[dict[str, Any]] = Field(..., min_length=1)

    _parsed: list[MathQuestion | CodingQuestion | McqQuestion | CodingMcqQuestion] = PrivateAttr(
        default_factory=list
    )

    @field_validator("schema_version")
    @classmethod
    def _version(cls, v: int) -> int:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {v} (expected {SCHEMA_VERSION})")
        return v

    @model_validator(mode="after")
    def _typed_questions(self) -> ContentFile:
        model = _KIND_MODELS[self.kind]
        seen: set[str] = set()
        parsed = []
        for raw in self.questions:
            q = model.model_validate(raw)
            if q.id in seen:
                raise ValueError(f"duplicate question id {q.id!r} in topic {self.topic.topic_id}")
            seen.add(q.id)
            parsed.append(q)
        self._parsed = parsed
        return self

    @property
    def parsed_questions(
        self,
    ) -> list[MathQuestion | CodingQuestion | McqQuestion | CodingMcqQuestion]:
        return list(self._parsed)


_KIND_MODELS: dict[str, type[BaseModel]] = {
    "math": MathQuestion,
    "coding": CodingQuestion,
    "mcq": McqQuestion,
    "coding_mcq": CodingMcqQuestion,
}
