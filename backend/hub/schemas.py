from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ReadingIn(BaseModel):
    slug: str
    value_numeric: float | None = None
    value_json: dict[str, Any] | None = None
    recorded_at: datetime | None = None
    session_id: int | None = None
    source_device: str | None = None
    client_event_id: str | None = None


class ReadingsBatchIn(BaseModel):
    readings: list[ReadingIn]


class SessionStartIn(BaseModel):
    session_type: str
    metadata: dict[str, Any] | None = None


class SessionPatchIn(BaseModel):
    ended_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class PluginToggleIn(BaseModel):
    plugin_id: str
    enabled: bool
    config: dict[str, Any] | None = None
