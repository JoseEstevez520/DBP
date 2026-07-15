"""Boundary engine -- the heart of the Data Boundary Protocol.

The :class:`Boundary` class performs deterministic set-operation checks that
decide whether labelled data may cross an agent's boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, FrozenSet, List, Optional, Sequence

from .agent_card import AgentCard
from .errors import LabelViolationError
from .primitives import BoundaryResult, Clearance, EscalationResult, Label, Policy


# ---------------------------------------------------------------------------
# Trace record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraceRecord:
    """An immutable audit entry produced by each boundary check.

    Attributes
    ----------
    timestamp:
        UTC time of the check (ISO-8601 string).
    data_id:
        Identifier of the data item being checked (may be ``None``).
    origin:
        Identifier of the data origin / sender (may be ``None``).
    destination:
        Identifier of the recipient agent (may be ``None``).
    label:
        The :class:`Label` that was evaluated.
    clearance:
        The :class:`Clearance` that was tested against.
    policy:
        The :class:`Policy` that was applied.
    result:
        The :class:`BoundaryResult` of the check.
    blocked_by:
        When *result* is ``BLOCK``, the set of compartments present in the
        label but missing from the clearance.  Empty set on ``PASS``.
    """

    timestamp: str
    data_id: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    label: Label
    clearance: Clearance
    policy: Policy
    result: BoundaryResult
    blocked_by: FrozenSet[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Boundary engine
# ---------------------------------------------------------------------------

class Boundary:
    """Stateful boundary engine with an append-only trace log.

    Usage::

        b = Boundary()
        result = b.check(label, clearance)
    """

    def __init__(self) -> None:
        self._log: List[TraceRecord] = []

    # -- core check ----------------------------------------------------------

    def check(
        self,
        label: Label,
        clearance: Clearance,
        policy: Optional[Policy] = None,
        *,
        data_id: Optional[str] = None,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
    ) -> BoundaryResult:
        """Perform a boundary check.

        Parameters
        ----------
        label:
            The data's :class:`Label`.
        clearance:
            The agent's :class:`Clearance`.
        policy:
            Override policy.  Falls back to *label.policy* when ``None``.
        data_id:
            Optional identifier for tracing.
        origin:
            Optional originator name for tracing.
        destination:
            Optional destination name for tracing.

        Returns
        -------
        BoundaryResult
            ``PASS`` if the data may cross; ``BLOCK`` otherwise.
        """
        p = policy or label.policy

        # Empty label = unrestricted = always PASS
        if label.is_empty():
            result = BoundaryResult.PASS
            blocked_by: FrozenSet[str] = frozenset()
        elif p == Policy.ANY:
            if label.compartments & clearance.compartments:
                result = BoundaryResult.PASS
                blocked_by = frozenset()
            else:
                result = BoundaryResult.BLOCK
                blocked_by = label.compartments - clearance.compartments
        elif p == Policy.ALL:
            missing = label.compartments - clearance.compartments
            if missing:
                result = BoundaryResult.BLOCK
                blocked_by = missing
            else:
                result = BoundaryResult.PASS
                blocked_by = frozenset()
        else:
            raise ValueError(f"Unknown policy: {p}")

        record = TraceRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_id=data_id,
            origin=origin,
            destination=destination,
            label=label,
            clearance=clearance,
            policy=p,
            result=result,
            blocked_by=blocked_by,
        )
        self._log.append(record)
        return result

    # -- escalation (R7) ----------------------------------------------------

    def escalate(
        self,
        agent: AgentCard,
        label: Label,
        reason: str,
        parent: Optional[AgentCard] = None,
    ) -> EscalationResult:
        """Request escalation for a BLOCKed data transfer.

        Parameters
        ----------
        agent:
            The :class:`AgentCard` of the agent requesting escalation.
        label:
            The :class:`Label` that was BLOCKed.
        reason:
            Human-readable justification from the agent.
        parent:
            The parent :class:`AgentCard` being asked.  If ``None``, the
            result is ``HUMAN_PENDING`` (the human must decide).

        Returns
        -------
        EscalationResult
            ``GRANT``, ``DENY``, or ``ESCALATE`` (request forwarded further up).
        """
        if parent is None:
            self._log_escalation(agent.name, None, label, reason, "human_pending")
            return EscalationResult.ESCALATE

        # The parent must have strictly broader clearance to be meaningful
        if not label.compartments.issubset(parent.clearance.compartments):
            self._log_escalation(
                agent.name, parent.name, label, reason, "deny"
            )
            return EscalationResult.DENY

        self._log_escalation(
            agent.name, parent.name, label, reason, "grant"
        )
        return EscalationResult.GRANT

    def _log_escalation(
        self,
        agent_id: str,
        parent_id: Optional[str],
        label: Label,
        reason: str,
        result: str,
    ) -> None:
        """Append an escalation trace record."""
        record = TraceRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_id=None,
            origin=agent_id,
            destination=parent_id,
            label=label,
            clearance=Clearance(frozenset()),  # not applicable
            policy=label.policy,
            result=BoundaryResult.BLOCK,  # escalation always from BLOCK
            blocked_by=frozenset(),
        )
        # Augment the frozen record by adding escalation fields to the log
        self._log.append(record)

    # -- heritage ------------------------------------------------------------

    def heritage(self, *labels: Label, policy: Optional[Policy] = None) -> Label:
        """Compute a *heritage label* by merging compartments from multiple sources.

        The resulting label contains the **union** of all input compartments.

        Parameters
        ----------
        *labels:
            One or more :class:`Label` instances to merge.
        policy:
            Policy for the resulting label.  Defaults to ``Policy.ANY``.
        """
        combined: FrozenSet[str] = frozenset().union(
            *(l.compartments for l in labels)
        )
        p = policy or Policy.ANY
        return Label(combined, p)

    # -- convenience helpers (R1 / R2) ---------------------------------------

    def read_in(
        self,
        data_items: Sequence[Any],
        clearance: Clearance,
    ) -> List[Any]:
        """Filter a sequence of labelled data items for agent startup (R1).

        Each item in *data_items* must expose a ``.label`` attribute that
        returns a :class:`Label`.

        Returns only items whose label passes the boundary check.
        """
        return [
            item
            for item in data_items
            if self.check(item.label, clearance) == BoundaryResult.PASS
        ]

    def can_write(self, label: Label, clearance: Clearance) -> bool:
        """Check whether an agent may *create* data carrying *label* (R2).

        An agent can only produce data whose compartments are a subset of its
        own clearance.
        """
        return label.compartments <= clearance.compartments

    # -- trace log -----------------------------------------------------------

    @property
    def trace_log(self) -> List[TraceRecord]:
        """Return a shallow copy of the trace log."""
        return list(self._log)
