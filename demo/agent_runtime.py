"""Agent runtime — spawns and manages multiple DBP agents."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    DBPMessage,
    Label,
    Policy,
    Registry,
)
from dbp.transport.local import LocalTransport

from .agent_base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRuntimeError(Exception):
    """Runtime-level error."""


class AgentRuntime:
    """Manages multiple agents that communicate via DBP.

    Each agent has its own inbox directory under ``base_path / inboxes / <name>``.
    Messages are routed through :class:`LocalTransport`, which enforces
    boundary checks before delivery.

    Usage::

        runtime = AgentRuntime(base_path=Path("./agent_workspace"))
        runtime.add_agent(agent)
        runtime.start()
        runtime.send_message("alice", "bob", {"text": "hello"}, Label({"greeting"}))
        runtime.run_cycle()
        runtime.stop()
    """

    def __init__(self, base_path: Path) -> None:
        self.base_path = Path(base_path)
        self.boundary = Boundary()
        self.registry = Registry()
        self._agents: Dict[str, Tuple[BaseAgent, LocalTransport]] = {}
        self._running = False

    # -- lifecycle -----------------------------------------------------------

    def add_agent(self, agent: BaseAgent) -> None:
        """Register *agent* and create its inbox directory."""
        card = agent.card
        self.registry.register(card)
        inbox = self.base_path / "inboxes" / card.name
        transport = LocalTransport(self.boundary, inbox)
        self._agents[card.name] = (agent, transport)
        logger.info("Registered agent '%s' (clearance=%s)", card.name, sorted(card.clearance.compartments))

    def start(self) -> None:
        """Start the runtime (currently a no-op but reserved for lifecycle)."""
        self._running = True
        logger.info("Runtime started — %d agent(s) registered", len(self._agents))

    def stop(self) -> None:
        """Stop the runtime and clean up inbox directories."""
        self._running = False
        inbox_root = self.base_path / "inboxes"
        if inbox_root.exists():
            shutil.rmtree(inbox_root)
        logger.info("Runtime stopped")

    # -- messaging -----------------------------------------------------------

    def send_message(
        self,
        sender_name: str,
        recipient_name: str,
        payload: Dict[str, Any],
        label: Label,
        policy: Policy = Policy.ANY,
    ) -> BoundaryResult:
        """Send a *payload* from *sender_name* to *recipient_name*.

        The message goes through the recipient's :class:`LocalTransport`,
        which performs a DBP boundary check before writing to disk.

        Returns ``PASS`` or ``BLOCK``.
        """
        if sender_name not in self._agents:
            raise AgentRuntimeError(f"Unknown sender: {sender_name}")
        if recipient_name not in self._agents:
            raise AgentRuntimeError(f"Unknown recipient: {recipient_name}")

        sender_card = self.registry.get(sender_name)
        recipient_card = self.registry.get(recipient_name)
        _recip_agent, recip_transport = self._agents[recipient_name]

        msg = DBPMessage(
            id="",
            label=label,
            origin=sender_name,
            destination=recipient_name,
            payload=payload,
            policy=policy,
        )
        result = recip_transport.send(msg, sender_card, recipient_card)
        if result == BoundaryResult.PASS:
            logger.debug(
                "%s -> %s: PASS (label=%s, policy=%s)",
                sender_name,
                recipient_name,
                sorted(label.compartments),
                policy.value,
            )
        else:
            logger.debug(
                "%s -> %s: BLOCK (label=%s, policy=%s)",
                sender_name,
                recipient_name,
                sorted(label.compartments),
                policy.value,
            )
        return result

    # -- cycle ---------------------------------------------------------------

    def run_cycle(self) -> None:
        """Run one processing cycle for every agent.

        For each agent:
        1. Read pending messages from its inbox.
        2. Pass each through the agent's *process_message* handler.
        3. If the handler returns a response, send it back to the origin.
        4. Invoke the agent's *act* hook for autonomous behaviour.
        """
        if not self._running:
            raise AgentRuntimeError("Runtime is not started — call start() first")

        for name in list(self._agents):
            agent, transport = self._agents[name]
            card = agent.card

            # 1. Receive
            inbox_msgs = transport.receive(card)

            # 2. Process each message
            for msg in inbox_msgs:
                response = agent.process_message(msg)
                if response is not None:
                    self.send_message(
                        sender_name=name,
                        recipient_name=msg.origin,
                        payload=response.payload,
                        label=response.label,
                        policy=response.policy,
                    )

            # 3. Clean up delivered messages
            for msg in inbox_msgs:
                msg_path = transport.base_path / f"{msg.id}.md"
                if msg_path.exists():
                    msg_path.unlink()

            # 4. Autonomous action
            agent.act(self)

    def run_cycles(self, n: int) -> None:
        """Run *n* cycles."""
        for i in range(n):
            logger.debug("--- Cycle %d/%d ---", i + 1, n)
            self.run_cycle()

    # -- convenience ---------------------------------------------------------

    @property
    def trace_log(self):
        """Shortcut to the shared boundary engine's trace log."""
        return self.boundary.trace_log

    def _repr_messages(
        self,
    ) -> List[Dict[str, Any]]:
        """Pretty-print summary of every trace record."""
        out = []
        for rec in self.trace_log:
            origin = rec.origin or "?"
            dest = rec.destination or "?"
            out.append({
                "ts": rec.timestamp,
                "from": origin,
                "to": dest,
                "label": sorted(rec.label.compartments),
                "result": rec.result.value,
                "policy": rec.policy.value,
                "blocked_by": sorted(rec.blocked_by) if rec.blocked_by else [],
            })
        return out
