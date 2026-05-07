from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class SensorEvent:
    machine_id: str
    timestamp: datetime
    variable: str
    value: float

    @property
    def event_id(self) -> str:
        raw = f"{self.machine_id}|{self.timestamp.astimezone(timezone.utc).isoformat()}|{self.variable}|{self.value}"
        return sha256(raw.encode()).hexdigest()

    def to_ndjson_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "machine_id": self.machine_id,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "variable": self.variable,
            "value": self.value,
        }