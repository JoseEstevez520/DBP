"""Core DBP primitives: Label, Clearance, Policy, and BoundaryResult.

These are the fundamental building blocks of the Data Boundary Protocol.
All are immutable value objects suitable for use as dict keys or set members.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Iterable, Union

from .errors import EmptyClearanceError


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Policy(Enum):
    """Determines how compartment overlap is evaluated.

    * ``ANY`` -- at least one compartment must match (set intersection).
    * ``ALL`` -- every compartment in the label must be present in the
      clearance (subset check).
    """

    ANY = "any"
    ALL = "all"


class EscalationResult(Enum):
    """Outcome of an escalation request (R7)."""

    GRANT = "grant"
    DENY = "deny"
    ESCALATE = "escalate"


class BoundaryResult(Enum):
    """Outcome of a boundary check."""

    PASS = "pass"
    BLOCK = "block"


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Label:
    """A data label consisting of zero or more compartment strings.

    An *empty* label (no compartments) is treated as unrestricted -- it will
    always pass any boundary check regardless of the agent's clearance.

    Parameters
    ----------
    compartments:
        Any iterable of strings (``set``, ``list``, ``frozenset``, ...).
    policy:
        Default evaluation policy when none is supplied at check time.
    """

    compartments: FrozenSet[str]
    policy: Policy = Policy.ANY

    def __init__(
        self,
        compartments: Union[FrozenSet[str], Iterable[str]],
        policy: Policy = Policy.ANY,
    ) -> None:
        cs = (
            compartments
            if isinstance(compartments, frozenset)
            else frozenset(compartments)
        )
        object.__setattr__(self, "compartments", cs)
        object.__setattr__(self, "policy", policy)

    # -- helpers -------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return ``True`` when the label carries no compartments."""
        return len(self.compartments) == 0


# ---------------------------------------------------------------------------
# Clearance
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Clearance:
    """An agent's clearance -- the set of compartments it is allowed to access.

    A clearance **must not** be empty; constructing one with an empty iterable
    raises :class:`EmptyClearanceError`.

    Parameters
    ----------
    compartments:
        Any non-empty iterable of strings.
    """

    compartments: FrozenSet[str]

    def __init__(
        self,
        compartments: Union[FrozenSet[str], Iterable[str]],
    ) -> None:
        cs = (
            compartments
            if isinstance(compartments, frozenset)
            else frozenset(compartments)
        )
        if len(cs) == 0:
            raise EmptyClearanceError("Clearance MUST NOT be empty")
        object.__setattr__(self, "compartments", cs)
