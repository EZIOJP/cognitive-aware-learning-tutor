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
