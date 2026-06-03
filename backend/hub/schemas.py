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


class MetricDefIn(BaseModel):
    label: str
    slug: str
    unit: str = "count"
    source_type: str = "manual"


class CustomFeatureIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    feature_slug: str = Field(min_length=2, max_length=33)
    metrics: list[MetricDefIn] = Field(min_length=1, max_length=20)


class CustomFeaturePatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    enabled: bool | None = None


class AddMetricIn(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=2, max_length=49)
    unit: str = "count"
    source_type: str = "manual"


class DashboardLayoutIn(BaseModel):
    widget_state: dict[str, Any] = Field(default_factory=dict)
    widget_order: list[str] = Field(default_factory=list)
    focus_mode: bool = False
