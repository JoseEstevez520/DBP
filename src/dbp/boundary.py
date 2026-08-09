"""Boundary engine -- the heart of the Data Boundary Protocol.

The :class:`Boundary` class performs deterministic set-operation checks that
decide whether labelled data may cross an agent's boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, FrozenSet, List, Optional, Sequence, Tuple

from .agent_card import AgentCard
from .primitives import BoundaryResult, Clearance, EscalationResult, Label, Policy
from .registry import Registry


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
# Escalation outcome
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EscalationOutcome:
    """Result of walking an escalation chain (R7).

    Attributes
    ----------
    result:
        The :class:`EscalationResult` the chain resolved to.
    authority:
        Name of the agent that resolved the request (``None`` when the chain
        reached the human backstop without an agent granting).
    chain:
        The names visited, in order, from the first parent upward.
    derived_label:
        When *result* is ``GRANT_DERIVED``, the label of the derived artifact
        (boundary-safe for the requester). ``None`` otherwise.
    derived:
        When *result* is ``GRANT_DERIVED``, the derived artifact the authority
        chose to reveal. ``None`` otherwise.
    """

    result: EscalationResult
    authority: Optional[str]
    chain: Tuple[str, ...]
    derived_label: Optional[Label] = None
    derived: Any = None


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
        if not isinstance(clearance, Clearance):
            raise TypeError(
                f"clearance must be a Clearance instance, got {type(clearance).__name__}"
            )
        if not isinstance(label, Label):
            raise TypeError(
                f"label must be a Label instance, got {type(label).__name__}"
            )

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
        # GRANT also records a PASS trace so the audit trail reflects the
        # effective override
        self._log.append(
            TraceRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                data_id=None,
                origin=agent.name,
                destination=parent.name,
                label=label,
                clearance=parent.clearance,
                policy=label.policy,
                result=BoundaryResult.PASS,
                blocked_by=frozenset(),
            )
        )
        return EscalationResult.GRANT

    # -- hierarchical escalation (R7) ---------------------------------------

    def escalate_chain(
        self,
        agent: AgentCard,
        label: Label,
        reason: str,
        registry: Registry,
        *,
        derive: Optional[Callable[[AgentCard, Label], Tuple[Any, Label]]] = None,
        max_hops: int = 64,
    ) -> EscalationOutcome:
        """Walk the escalation hierarchy until an authority resolves the request.

        The request rises through each agent's ``escalation_parent`` link
        (resolved via *registry*) until an ancestor with sufficient clearance
        answers, or the chain ends and the human becomes the final authority.

        Two ways an authority may answer:

        * **Derived** (preferred) -- when *derive* is supplied, the first
          ancestor cleared for *label* produces a derived artifact via
          ``derive(authority, label)``. The artifact's label must itself pass a
          boundary check for the **original requester**; if it would still leak,
          the answer is ``DENY``. The raw data never crosses -> ``GRANT_DERIVED``.
        * **Raw override** (escape hatch) -- when *derive* is ``None``, a cleared
          ancestor approves a raw override -> ``GRANT`` (as :meth:`escalate`).

        Parameters
        ----------
        agent:
            The requesting agent's card. Its ``escalation_parent`` starts the walk.
        label:
            The blocked data label.
        reason:
            Human-readable justification, recorded per hop.
        registry:
            The :class:`Registry` used to resolve ``escalation_parent`` names.
        derive:
            Optional callback ``(authority, label) -> (value, derived_label)`` that
            lets the answering authority reveal a boundary-safe derivative instead
            of the raw data.
        max_hops:
            Cycle guard; raises :class:`EscalationError` if exceeded.

        Returns
        -------
        EscalationOutcome
            The resolved result, the authority (or ``None`` for the human), and
            the chain that was walked.
        """
        # Imported lazily to keep the error family in one place without a cycle.
        from .errors import EscalationError

        chain: List[str] = []
        current = agent
        hops = 0

        while True:
            parent_name = current.escalation_parent
            if parent_name is None:
                # Top of the agent chain: the human is the final authority.
                self._log_escalation(current.name, None, label, reason, "human_pending")
                return EscalationOutcome(
                    EscalationResult.ESCALATE, None, tuple(chain)
                )

            parent = registry.get(parent_name)
            if parent is None:
                raise EscalationError(
                    f"escalation_parent '{parent_name}' of '{current.name}' "
                    "is not registered"
                )

            hops += 1
            if hops > max_hops:
                raise EscalationError(
                    f"escalation chain exceeded {max_hops} hops (possible cycle)"
                )
            chain.append(parent.name)

            authorised = label.compartments.issubset(parent.clearance.compartments)
            if not authorised:
                # This ancestor lacks the clearance to decide; forward upward.
                self._log_escalation(agent.name, parent.name, label, reason, "escalate")
                current = parent
                continue

            if derive is not None:
                derived_value, derived_label = derive(parent, label)
                # The derivative must be safe for the ORIGINAL requester, else
                # answering would just leak the data one level down.
                safe = self.check(
                    derived_label,
                    agent.clearance,
                    origin=parent.name,
                    destination=agent.name,
                )
                if safe is BoundaryResult.BLOCK:
                    self._log_escalation(agent.name, parent.name, label, reason, "deny")
                    return EscalationOutcome(
                        EscalationResult.DENY, parent.name, tuple(chain)
                    )
                self._log_escalation(
                    agent.name, parent.name, label, reason, "grant_derived"
                )
                return EscalationOutcome(
                    EscalationResult.GRANT_DERIVED,
                    parent.name,
                    tuple(chain),
                    derived_label,
                    derived_value,
                )

            # Raw override escape hatch (parity with single-hop escalate()).
            self._log_escalation(agent.name, parent.name, label, reason, "grant")
            self._log.append(
                TraceRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    data_id=None,
                    origin=agent.name,
                    destination=parent.name,
                    label=label,
                    clearance=parent.clearance,
                    policy=label.policy,
                    result=BoundaryResult.PASS,
                    blocked_by=frozenset(),
                )
            )
            return EscalationOutcome(
                EscalationResult.GRANT, parent.name, tuple(chain)
            )

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
            clearance=Clearance({"__escalation__"}),
            policy=label.policy,
            result=BoundaryResult.BLOCK,
            blocked_by=frozenset(),
        )
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

        Raises
        ------
        ValueError
            If no labels are provided.
        """
        for i, l in enumerate(labels):
            if not isinstance(l, Label):
                raise TypeError(
                    f"Argument {i} must be a Label instance, got {type(l).__name__}"
                )
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
