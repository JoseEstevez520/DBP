"""Agent Card -- identity and clearance for a DBP agent.

An :class:`AgentCard` declares what compartments an agent is cleared for,
along with optional metadata (description, endpoint, auth).  Cards are
typically stored as JSON files and loaded at startup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .primitives import Clearance


@dataclass
class AgentCard:
    """An agent's identity and clearance declaration.

    Parameters
    ----------
    name:
        Human-readable agent name (must be unique within a registry).
    clearance:
        The :class:`Clearance` the agent holds.
    description:
        Free-text description of the agent's purpose.
    endpoint:
        Network endpoint (URL) where the agent listens, if applicable.
    auth:
        Optional authentication metadata (e.g. ``{"type": "bearer", ...}``).
    protocol:
        Protocol version string.
    """

    name: str
    clearance: Clearance
    description: str = ""
    endpoint: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    protocol: str = "dbp/1.0"

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the card to a plain dictionary."""
        return {
            "name": self.name,
            "clearance": sorted(self.clearance.compartments),
            "description": self.description,
            "endpoint": self.endpoint,
            "auth": self.auth,
            "protocol": self.protocol,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentCard:
        """Construct an :class:`AgentCard` from a dictionary."""
        return cls(
            name=data["name"],
            clearance=Clearance(data["clearance"]),
            description=data.get("description", ""),
            endpoint=data.get("endpoint"),
            auth=data.get("auth"),
            protocol=data.get("protocol", "dbp/1.0"),
        )

    # -- JSON file I/O -------------------------------------------------------

    @classmethod
    def from_json_file(cls, path: str) -> AgentCard:
        """Load an :class:`AgentCard` from a JSON file on disk."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)

    def to_json_file(self, path: str) -> None:
        """Write the card to a JSON file on disk."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
