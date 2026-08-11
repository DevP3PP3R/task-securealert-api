from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

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

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, value):
        if not isinstance(value, str):
            raise ValueError(
                "timestamp must be an ISO 8601 datetime string"
            )

        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "timestamp must be an ISO 8601 datetime string"
            ) from exc