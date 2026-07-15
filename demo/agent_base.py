"""Base agent for the DBP Agent Runtime."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from dbp import AgentCard, DBPMessage

logger = logging.getLogger(__name__)


class BaseAgent:
    """An agent that communicates via DBP.

    Each agent runs inside an :class:`AgentRuntime` and has:

    * An :class:`AgentCard` with its identity and clearance.
    * A *process* callback invoked for each incoming message.
    * An *act* callback invoked every cycle for autonomous behaviour.

    Parameters
    ----------
    card:
        The agent's identity and clearance.
    process_msg:
        Optional callable ``(agent, message) -> DBPMessage | None``.
        Return a response message or ``None`` to stay silent.
    act:
        Optional callable ``(agent, runtime) -> None``.
        Called every cycle to let the agent initiate actions.
    """

    def __init__(
        self,
        card: AgentCard,
        process_msg: Optional[Callable[["BaseAgent", DBPMessage], Optional[DBPMessage]]] = None,
        act: Optional[Callable[["BaseAgent", "AgentRuntime"], None]] = None,
    ) -> None:
        self.card = card
        self._process_msg = process_msg
        self._act = act

    # -- public API ----------------------------------------------------------

    @property
    def name(self) -> str:
        return self.card.name

    def process_message(self, msg: DBPMessage) -> Optional[DBPMessage]:
        """Handle an incoming message.

        Override in subclasses or pass a *process_msg* callable to the
        constructor.
        """
        if self._process_msg is not None:
            return self._process_msg(self, msg)
        logger.debug("%s: no process handler — ignoring message", self.name)
        return None

    def act(self, runtime: "AgentRuntime") -> None:
        """Autonomous action hook called every cycle.

        Override in subclasses or pass an *act* callable to the constructor.
        """
        if self._act is not None:
            self._act(self, runtime)
