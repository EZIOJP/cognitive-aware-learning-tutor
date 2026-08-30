from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MathQuestionIn(BaseModel):
    """Single imported question — extra keys allowed until format is finalized."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    topic: str | None = None
    prompt: str | None = Field(None, alias="question")
    expected_answer: str | None = Field(None, alias="answer")
    explanation: str | None = None
    latex: str | None = None
    difficulty: str | None = None
    answer_format: str | None = None
    tags: list[str] | None = None
    external_id: str | None = None
    source: str | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool = True


class MathImportBundle(BaseModel):
    """Draft import envelope — `format_version` reserved for later."""

    model_config = ConfigDict(extra="allow")

    format_version: int = 1
    topic: str | None = None
    source: str | None = None
    questions: list[MathQuestionIn] = Field(default_factory=list)


class MathImportResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    errors: list[str]
    total_in_bank: int
