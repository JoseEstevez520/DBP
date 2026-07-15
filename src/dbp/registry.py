"""Agent registry for discovery and lookup.

The :class:`Registry` provides a simple in-memory store where
:class:`AgentCard` instances can be registered and queried by name or
compartment.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .agent_card import AgentCard


class Registry:
    """In-memory agent registry.

    Usage::

        reg = Registry()
        reg.register(card)
        card = reg.get("my-agent")
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentCard] = {}

    def register(self, card: AgentCard) -> None:
        """Register an agent card.

        Parameters
        ----------
        card:
            The :class:`AgentCard` to register.  If a card with the same
            name already exists it will be replaced.
        """
        self._agents[card.name] = card

    def get(self, name: str) -> Optional[AgentCard]:
        """Retrieve a registered card by name.

        Returns ``None`` if no card with that name exists.
        """
        return self._agents.get(name)

    def list_agents(self) -> List[AgentCard]:
        """Return all registered agent cards."""
        return list(self._agents.values())

    def find_by_compartment(self, compartment: str) -> List[AgentCard]:
        """Return all agents whose clearance includes *compartment*."""
        return [
            card
            for card in self._agents.values()
            if compartment in card.clearance.compartments
        ]
