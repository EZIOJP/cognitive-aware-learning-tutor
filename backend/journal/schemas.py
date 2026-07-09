from typing import Optional

from pydantic import BaseModel, Field


class JournalEntryCreate(BaseModel):
    entry_date: Optional[str] = None  # YYYY-MM-DD, default today
    title: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1)


class JournalEntryUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None, min_length=1)


class JournalEntryOut(BaseModel):
    id: int
    entry_date: str
    title: Optional[str] = None
    content: str
    updated_at: Optional[str] = None
