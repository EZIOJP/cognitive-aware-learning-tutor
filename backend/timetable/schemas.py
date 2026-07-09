import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

from backend.timetable.json_extract import extract_json_from_text


class TaskSchema(BaseModel):
    title: str
    description: Optional[str] = None


class ScheduleSlotSchema(BaseModel):
    """Weekly grid cell — day + time window linked to a task index."""
    day: str = Field(..., description="mon|tue|wed|thu|fri|sat|sun or 0-6")
    start: str = Field(..., description="HH:MM 24h")
    end: str = Field(..., description="HH:MM 24h")
    task_index: int = Field(ge=0)
    title: Optional[str] = None


class TrackedSessionSync(BaseModel):
    session_id: str
    task_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    source: str = "manual"
    category: Optional[str] = None
    productivity_score: Optional[int] = None


class SyncPayload(BaseModel):
    name: str
    tasks: List[TaskSchema] = []
    slots: List[ScheduleSlotSchema] = []
    sessions: List[TrackedSessionSync] = []
    replace: bool = False

    @model_validator(mode='after')
    def check_overlapping_sessions(self) -> Self:
        sorted_sessions = sorted(self.sessions, key=lambda x: x.start_time)

        for i in range(len(sorted_sessions) - 1):
            current = sorted_sessions[i]
            next_sess = sorted_sessions[i + 1]
            if next_sess.start_time < current.end_time:
                raise ValueError(
                    f"Constraint Violation: Overlapping sessions detected between "
                    f"'{current.session_id}' and '{next_sess.session_id}'"
                )

        return self


class DailySlotSchema(BaseModel):
    """Single-day schedule entry (no weekday)."""
    start: str = Field(..., description="HH:MM 24h")
    end: Optional[str] = Field(None, description="HH:MM 24h")
    duration_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    title: str
    category: str = "study"
    color: Optional[str] = None
    task_index: Optional[int] = None


class ImportJsonPayload(BaseModel):
    """JSON file import — weekly, daily, or mixed."""
    name: Optional[str] = None
    schedule_type: str = "weekly"  # weekly | daily
    date: Optional[str] = None  # YYYY-MM-DD for daily
    tasks: List[TaskSchema] = []
    slots: List[ScheduleSlotSchema] = []
    daily_slots: List[DailySlotSchema] = []
    sessions: List[TrackedSessionSync] = []
    replace: bool = False
    apply_to_planner: bool = False

    @classmethod
    def from_raw(cls, data: dict) -> "ImportJsonPayload":
        root = data.get("timetable") if isinstance(data.get("timetable"), dict) else data
        name = root.get("name") or data.get("name") or "Imported timetable"

        schedule_type = str(root.get("type") or root.get("schedule_type") or "weekly").lower()
        if root.get("date") and not root.get("slots") and root.get("daily_slots"):
            schedule_type = "daily"
        if root.get("date") and root.get("slots") and not any(s.get("day") for s in root.get("slots", []) if isinstance(s, dict)):
            schedule_type = "daily"

        daily_slots_raw = root.get("daily_slots") or []
        if schedule_type == "daily" and not daily_slots_raw and root.get("slots"):
            # Slots without day field → treat as daily
            daily_slots_raw = root.get("slots", [])

        return cls(
            name=str(name),
            schedule_type=schedule_type,
            date=root.get("date") or data.get("date"),
            tasks=[TaskSchema.model_validate(t) for t in root.get("tasks", [])],
            slots=[ScheduleSlotSchema.model_validate(s) for s in root.get("slots", []) if s.get("day")],
            daily_slots=[DailySlotSchema.model_validate(s) for s in daily_slots_raw],
            sessions=[TrackedSessionSync.model_validate(s) for s in root.get("sessions", [])],
            replace=bool(root.get("replace", data.get("replace", False))),
            apply_to_planner=bool(root.get("apply_to_planner", data.get("apply_to_planner", False))),
        )

    @classmethod
    def from_text(cls, text: str) -> "ImportJsonPayload":
        data = extract_json_from_text(text)
        if not isinstance(data, dict):
            raise ValueError("JSON root must be an object")
        return cls.from_raw(data)


def slots_to_json(slots: List[ScheduleSlotSchema]) -> str:
    return json.dumps([s.model_dump() for s in slots])
