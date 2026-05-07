from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from hashlib import sha256


@dataclass(frozen=True)
class SensorEvent:
    machine_id: str
    timestamp: datetime
    variable: str
    value: float

    @property
    def event_id(self) -> str:
        raw = (
            f"{self.machine_id}|"
            f"{self.timestamp.astimezone(timezone.utc).isoformat()}|"
            f"{self.variable}|"
            f"{self.value}"
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def to_ndjson_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_id"] = self.event_id
        d["timestamp"] = (
            self.timestamp.astimezone(timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        return d