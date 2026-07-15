"""Data Boundary Protocol (DBP) -- reference implementation.

This package provides the core building blocks for enforcing data-boundary
checks between AI agents:

* **Primitives** -- :class:`Label`, :class:`Clearance`, :class:`Policy`,
  :class:`BoundaryResult`
* **Boundary engine** -- :class:`Boundary`, :class:`Heritage`
  (via :meth:`Boundary.heritage`)
* **Messages** -- :class:`DBPMessage`
* **Agent cards** -- :class:`AgentCard`
* **Registry** -- :class:`Registry`
* **Transports** -- ``dbp.transport.local``, ``dbp.transport.http``
"""

from .agent_card import AgentCard
from .boundary import Boundary, TraceRecord
from .errors import (
    BoundaryCheckError,
    DBPError,
    EmptyClearanceError,
    InvalidMessageError,
    LabelViolationError,
)
from .message import DBPMessage
from .primitives import BoundaryResult, Clearance, Label, Policy
from .registry import Registry

# Heritage is exposed as an alias pointing to Boundary.heritage (the method).
# Users call ``boundary.heritage(label1, label2)`` -- the class itself is
# re-exported here for discoverability.
Heritage = Boundary.heritage

__all__ = [
    # Primitives
    "Label",
    "Clearance",
    "Policy",
    "BoundaryResult",
    # Engine
    "Boundary",
    "TraceRecord",
    "Heritage",
    # Messages
    "DBPMessage",
    # Agent cards
    "AgentCard",
    # Registry
    "Registry",
    # Errors
    "DBPError",
    "EmptyClearanceError",
    "LabelViolationError",
    "InvalidMessageError",
    "BoundaryCheckError",
]
