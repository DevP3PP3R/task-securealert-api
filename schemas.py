from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "motion_detected",
    "intrusion_alert",
    "camera_offline",
]

Severity = Literal[
    "low",
    "medium",
    "high"
]

class EventCreate(BaseModel):
    device_id: str = Field(min_length=3, max_length=64)
    event_type: EventType
    severity: Severity
    timestamp: datetime
    metadata: dict[str, Any] | None = None