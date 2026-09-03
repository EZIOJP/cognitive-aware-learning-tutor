from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PlannerBlockCreate(BaseModel):
    title: str
    category: str = "study"
    start_at: datetime
    duration_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    end_at: Optional[datetime] = None
    color: Optional[str] = None
    task_id: Optional[int] = None

    @model_validator(mode="after")
    def duration_or_end(self):
        if self.duration_minutes is None and self.end_at is None:
            raise ValueError("Provide duration_minutes or end_at")
        return self


class PlannerBlockUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    remaining_minutes: Optional[int] = Field(None, ge=0)
    color: Optional[str] = None
    status: Optional[str] = None


class CompleteBlockBody(BaseModel):
    minutes_spent: Optional[int] = Field(None, ge=0)


class RollForwardBody(BaseModel):
    new_start: Optional[datetime] = None


class GenerateWeekBody(BaseModel):
    timetable_id: Optional[int] = None
    week_start: Optional[datetime] = None


class ProposeFromExportBody(BaseModel):
    days: int = Field(7, ge=1, le=366)  # look-back for tracker export (max ~1 leap year)
    goals: Optional[str] = None
    week_start: Optional[str] = None  # YYYY-MM-DD (legacy alias for range_start)
    range_start: Optional[str] = None  # YYYY-MM-DD first day to fill
    horizon_days: int = Field(7, ge=1, le=62)  # how many days to propose
    use_llm: bool = True
    include_routines: bool = True
    # smart = gap-fill only; review = AI polish of draft_blocks; full = AI from scratch
    mode: Optional[str] = None  # "smart" | "review" | "full"
    draft_blocks: Optional[list[dict]] = None


class ApplyProposedBlocksBody(BaseModel):
    blocks: list[dict]


class GenerateDayBody(BaseModel):
    date: Optional[str] = None  # YYYY-MM-DD
    slots: Optional[list] = None
    skip_overlaps: bool = True


class RoutineCreate(BaseModel):
    title: str
    category: str = "personal"
    start_time: str
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    days: Optional[list[str]] = None
    color: Optional[str] = None
    enabled: bool = True
    sort_order: int = 0


class RoutineUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    days: Optional[list[str]] = None
    color: Optional[str] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class ApplyRoutinesBody(BaseModel):
    date: Optional[str] = None
    skip_overlaps: bool = True


class GoogleOAuthCredentialsBody(BaseModel):
    client_id: str = Field(..., min_length=10)
    client_secret: str = Field(..., min_length=5)


class ApplyDayRhythmBody(BaseModel):
    blocks: list[dict]
    day: Optional[str] = None  # YYYY-MM-DD


class MergeProposeBody(BaseModel):
    """Raw propose-from-export blocks → merged draft (same path as CALT Desktop)."""
    api_blocks: list[dict]
    range_start: Optional[str] = None  # YYYY-MM-DD
    horizon_days: int = Field(7, ge=1, le=62)


class ApplyMyDayBody(BaseModel):
    """Optional overrides — web passes goals/studyTasks from localStorage."""
    wake_hm: Optional[str] = None
    goals: Optional[str] = None  # pre-formatted prompt text
    study_tasks: Optional[list[dict]] = None
    snapshot: bool = True
