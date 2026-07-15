"""DBP message format with JSON serialisation.

A :class:`DBPMessage` is the unit of data exchange between agents in the
Data Boundary Protocol.  Every message carries a :class:`Label` so that
boundary checks can be performed before the payload crosses an agent's
boundary.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .errors import InvalidMessageError
from .primitives import Label, Policy


@dataclass
class DBPMessage:
    """A labelled message in the Data Boundary Protocol.

    Parameters
    ----------
    id:
        Unique message identifier.  Auto-generated (UUID4) when empty or ``None``.
    label:
        The data :class:`Label` governing boundary checks.
    origin:
        Identifier of the sending agent.
    payload:
        Arbitrary JSON-serialisable data.
    policy:
        Evaluation policy.  Defaults to ``Policy.ANY``.
    destination:
        Optional recipient agent identifier.
    timestamp:
        ISO-8601 timestamp.  Auto-generated (UTC now) when ``None``.
    protocol:
        Protocol version string.
    """

    id: str
    label: Label
    origin: str
    payload: Dict[str, Any]
    policy: Policy = Policy.ANY
    destination: Optional[str] = None
    timestamp: Optional[str] = None
    protocol: str = "dbp/1.0"

    def __post_init__(self) -> None:
        # Auto-generate id if not provided
        if not self.id:
            self.id = str(uuid.uuid4())
        # Auto-generate timestamp if not provided
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        # Validation
        if self.label is None:
            raise InvalidMessageError("label is required")
        if not isinstance(self.origin, str):
            raise InvalidMessageError(
                f"origin must be a string, got {type(self.origin).__name__}"
            )
        if not self.origin.strip():
            raise InvalidMessageError("origin is required")
        if self.payload is None:
            raise InvalidMessageError("payload is required")

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the message to a plain dictionary."""
        return {
            "id": self.id,
            "label": {
                "compartments": sorted(self.label.compartments),
                "policy": self.label.policy.value,
            },
            "origin": self.origin,
            "payload": self.payload,
            "policy": self.policy.value,
            "destination": self.destination,
            "timestamp": self.timestamp,
            "protocol": self.protocol,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DBPMessage:
        """Construct a :class:`DBPMessage` from a dictionary.

        Raises :class:`InvalidMessageError` on missing or malformed fields.
        """
        try:
            label_data = data["label"]
            label = Label(
                compartments=label_data["compartments"],
                policy=Policy(label_data.get("policy", "any")),
            )
            return cls(
                id=data.get("id", ""),
                label=label,
                origin=data["origin"],
                payload=data["payload"],
                policy=Policy(data.get("policy", "any")),
                destination=data.get("destination"),
                timestamp=data.get("timestamp"),
                protocol=data.get("protocol", "dbp/1.0"),
            )
        except KeyError as exc:
            raise InvalidMessageError(f"Missing required field: {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise InvalidMessageError(f"Invalid message data: {exc}") from exc

    def to_json(self) -> str:
        """Serialise the message to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> DBPMessage:
        """Deserialise a :class:`DBPMessage` from a JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise InvalidMessageError(f"Invalid JSON: {exc}") from exc
        return cls.from_dict(data)
